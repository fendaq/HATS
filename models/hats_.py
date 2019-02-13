import tensorflow as tf
import numpy as np
import functools
import metrics
import summary
from networks import ops
from algorithms import *


def sequence_lengths_fn(labels, blank, indices):

    print(labels)

    depth = len(labels.shape[1:]) - len(indices)
    begin = [0] + indices + [0] * depth
    size = [-1] + [1] * len(indices) + [-1] * depth

    labels = tf.squeeze(
        input=tf.slice(labels, begin, size),
        axis=list(range(1, len(indices) + 1))
    )

    return tf.count_nonzero(tf.reduce_any(
        input_tensor=tf.not_equal(labels, blank),
        axis=list(range(2, len(labels.shape)))
    ), axis=1)


def spatial_flatten(inputs, data_format):

    inputs_shape = inputs.shape.as_list()
    outputs_shape = ([-1, inputs_shape[1], np.prod(inputs_shape[2:])] if data_format == "channels_first" else
                     [-1, np.prod(inputs_shape[1:-1]), inputs_shape[-1]])

    return tf.reshape(inputs, outputs_shape)


class HATS(object):

    def __init__(self, backbone_network, attention_network,
                 num_units, num_classes, data_format, hyper_params):

        self.backbone_network = backbone_network
        self.attention_network = attention_network
        self.num_units = num_units
        self.num_classes = num_classes
        self.data_format = data_format
        self.hyper_params = hyper_params

    def __call__(self, images, labels, mode):

        feature_maps = self.backbone_network(
            inputs=images,
            training=mode == tf.estimator.ModeKeys.TRAIN
        )

        attention_maps = self.attention_network(
            inputs=feature_maps,
            sequence_lengths_fn=functools.partial(
                sequence_lengths_fn,
                labels=labels,
                blank=self.num_classes - 1
            ),
            training=mode == tf.estimator.ModeKeys.TRAIN
        )

        feature_vectors = map_innermost_element(
            function=lambda attention_maps: tf.layers.flatten(tf.matmul(
                a=spatial_flatten(feature_maps, self.data_format),
                b=spatial_flatten(attention_maps, self.data_format),
                transpose_a=False if self.data_format == "channels_first" else True,
                transpose_b=True if self.data_format == "channels_first" else False
            )),
            sequence=attention_maps
        )

        for i, num_units in enumerate(self.num_units):

            with tf.variable_scope("dense_block_{}".format(i)):

                feature_vectors = map_innermost_element(
                    function=compose(
                        lambda inputs: tf.layers.dense(
                            inputs=inputs,
                            units=num_units,
                            use_bias=False,
                            kernel_initializer=tf.initializers.variance_scaling(
                                scale=2.0,
                                mode="fan_in",
                                distribution="untruncated_normal"
                            ),
                            name="dense",
                            reuse=tf.AUTO_REUSE
                        ),
                        lambda inputs: ops.batch_normalization(
                            inputs=inputs,
                            data_format=self.data_format,
                            training=mode == tf.estimator.ModeKeys.TRAIN,
                            name="batch_normalization",
                            reuse=tf.AUTO_REUSE
                        ),
                        lambda inputs: tf.nn.relu(inputs)
                    ),
                    sequence=feature_vectors
                )

        logits = map_innermost_element(
            function=lambda feature_vectors: tf.layers.dense(
                inputs=feature_vectors,
                units=self.num_classes,
                kernel_initializer=tf.initializers.variance_scaling(
                    scale=1.0,
                    mode="fan_avg",
                    distribution="untruncated_normal"
                ),
                bias_initializer=tf.initializers.zeros(),
                name="logits",
                reuse=tf.AUTO_REUSE
            ),
            sequence=feature_vectors
        )

        predictions = map_innermost_element(
            function=lambda logits: tf.argmax(
                input=logits,
                axis=-1,
                output_type=tf.int32
            ),
            sequence=logits
        )
        # =========================================================================================
        # attention mapは可視化のためにチャンネルをマージする
        attention_maps = map_innermost_element(
            function=lambda attention_maps: tf.reduce_sum(
                input_tensor=attention_maps,
                axis=1 if self.data_format == "channels_first" else 3,
                keepdims=True
            ),
            sequence=attention_maps
        )
        # =========================================================================================
        # prediction mode
        if mode == tf.estimator.ModeKeys.PREDICT:

            while isinstance(predictions, list):

                predictions = map_innermost_list(
                    function=lambda predictions: tf.stack(predictions, axis=1),
                    sequence=predictions
                )

            while isinstance(attention_maps, list):

                attention_maps = map_innermost_list(
                    function=lambda attention_maps: tf.stack(attention_maps, axis=1),
                    sequence=attention_maps
                )

            return tf.estimator.EstimatorSpec(
                mode=mode,
                predictions=dict(
                    images=images,
                    predictions=predictions,
                    attention_maps=attention_maps
                )
            )
        # =========================================================================================
        # logits, predictions同様にlabelsもunstackしてnested listにしておく
        while all(flatten_innermost_element(map_innermost_element(lambda labels: len(labels.shape) > 1, labels))):
            labels = map_innermost_element(
                function=lambda labels: tf.unstack(labels, axis=1),
                sequence=labels
            )
        # =========================================================================================
        # 簡単のため，単語構造のみを残して残りはバッチ方向に展開
        # [batch_size, max_sequence_length_0, ..., max_equence_length_N, ...] =>
        # [batch_size * max_sequence_length_0 * ..., max_equence_length_N, ...]
        labels = tf.concat(flatten_innermost_element(map_innermost_list(
            function=lambda labels: tf.stack(labels, axis=1),
            sequence=labels
        )), axis=0)
        logits = tf.concat(flatten_innermost_element(map_innermost_list(
            function=lambda logits: tf.stack(logits, axis=1),
            sequence=logits
        )), axis=0)
        predictions = tf.concat(flatten_innermost_element(map_innermost_list(
            function=lambda predictions: tf.stack(predictions, axis=1),
            sequence=predictions
        )), axis=0)
        # =========================================================================================
        # Blankのみ含む単語(つまり存在しない)を削除
        indices = tf.where(tf.reduce_any(tf.not_equal(labels, self.num_classes - 1), axis=1))
        labels = tf.gather_nd(labels, indices)
        logits = tf.gather_nd(logits, indices)
        # =========================================================================================
        # lossがBlankを含まないようにマスク
        sequence_lengths = tf.count_nonzero(tf.not_equal(labels, self.num_classes - 1), axis=1)
        sequence_mask = tf.sequence_mask(sequence_lengths, labels.shape[-1], dtype=tf.int32)
        print(sequence_lengths.shape)
        # cross entropy loss
        loss = tf.contrib.seq2seq.sequence_loss(
            logits=logits,
            targets=labels,
            weights=tf.cast(sequence_mask, tf.float32),
            average_across_timesteps=True,
            average_across_batch=True
        )
        # =========================================================================================
        # Blankを除去した単語の正解率を求める
        word_accuracy = metrics.word_accuracy(
            labels=labels * sequence_mask,
            predictions=predictions * sequence_mask
        )
        edit_distance = metrics.edit_distance(
            labels=labels,
            logits=logits,
            sequence_lengths=sequence_lengths,
            normalize=True
        )
        print(edit_distance.shape)
        # =========================================================================================
        # tensorboard用のsummary
        tf.identity(word_accuracy[0], name="word_accuracy")
        summary.any(word_accuracy[1], name="word_accuracy")
        tf.identity(edit_distance[0], name="edit_distance")
        summary.any(edit_distance[1], name="edit_distance")

        summary.any(
            tensor=images,
            name="images",
            data_format=self.data_format,
            max_outputs=2
        )
        for indices, attention_maps in flatten_innermost_element(enumerate_innermost_element(attention_maps)):
            summary.any(
                tensor=attention_maps,
                name="attention_maps_{}".format("_".join(map(str, indices))),
                data_format=self.data_format,
                max_outputs=2
            )
        # =========================================================================================
        # training mode
        if mode == tf.estimator.ModeKeys.TRAIN:

            with tf.control_dependencies(tf.get_collection(tf.GraphKeys.UPDATE_OPS)):

                train_op = self.hyper_params.optimizer.minimize(
                    loss=loss,
                    global_step=tf.train.get_global_step()
                )

            return tf.estimator.EstimatorSpec(
                mode=mode,
                loss=loss,
                train_op=train_op
            )
        # =========================================================================================
        # evaluation mode
        if mode == tf.estimator.ModeKeys.EVAL:

            return tf.estimator.EstimatorSpec(
                mode=mode,
                loss=loss,
                eval_metric_ops=dict(
                    word_accuracy=word_accuracy,
                    edit_distance=edit_distance
                )
            )
        # =========================================================================================
