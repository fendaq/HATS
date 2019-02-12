import tensorflow as tf


def dense_to_sparse(tensor, null):

    indices = tf.where(tf.not_equal(tensor, null))
    values = tf.gather_nd(tensor, indices)
    shape = tf.shape(tensor, out_type=tf.int64)

    return tf.SparseTensor(indices, values, shape)


def edit_distance(labels, logits, normalize, name="edit_distance"):

    batch_size, time_step, num_classes = tf.unstack(tf.shape(logits))

    predictions = tf.nn.ctc_greedy_decoder(
        inputs=tf.transpose(logits, [1, 0, 2]),
        sequence_length=tf.tile([time_step], [batch_size]),
        merge_repeated=False
    )[0][0]

    labels = dense_to_sparse(labels, num_classes - 1)

    return tf.metrics.mean(tf.edit_distance(
        hypothesis=tf.cast(predictions, tf.int32),
        truth=tf.cast(labels, tf.int32),
        normalize=normalize,
        name=name
    ))


def word_accuracy(labels, predictions, name="word_accuracy"):

    return tf.metrics.mean(tf.reduce_all(tf.equal(predictions, labels), axis=1), name=name)
