# =============================================================
# dataset details
# dataset: chars74k
# download: http://www.ee.surrey.ac.uk/CVSSP/demos/chars74k/
# train: 11252
# test: 1251
# classes: [0-9A-Z](case-insensitive)
# =============================================================


import tensorflow as tf
import argparse
from attrdict import AttrDict
from dataset import Dataset
from models.classifier import Classifier
from networks.resnet import ResNet
from algorithms import *

parser = argparse.ArgumentParser()
parser.add_argument("--model_dir", type=str, default="chars74k_classifier", help="model directory")
parser.add_argument("--pretrained_model_dir", type=str, default="", help="pretrained model directory")
parser.add_argument('--filenames', type=str, nargs="+", default=["chars74k_train.tfrecord"], help="tfrecord filenames")
parser.add_argument("--num_epochs", type=int, default=1000, help="number of training epochs")
parser.add_argument("--batch_size", type=int, default=128, help="batch size")
parser.add_argument("--data_format", type=str, default="channels_first", help="data format")
parser.add_argument("--steps", type=int, default=None, help="number of training epochs")
parser.add_argument("--max_steps", type=int, default=None, help="maximum number of training epochs")
parser.add_argument("--train", action="store_true", help="with training")
parser.add_argument("--eval", action="store_true", help="with evaluation")
parser.add_argument("--predict", action="store_true", help="with prediction")
parser.add_argument("--gpu", type=str, default="0,1,2", help="gpu id")
parser.add_argument("--random_seed", type=int, default=1209, help="random seed")
args = parser.parse_args()

tf.logging.set_verbosity(tf.logging.INFO)


def main(unused_argv):

    classifier = tf.estimator.Estimator(
        model_fn=lambda features, labels, mode: Classifier(
            backbone_network=ResNet(
                conv_param=AttrDict(filters=64, kernel_size=[7, 7], strides=[2, 2]),
                pool_param=None,
                residual_params=[
                    AttrDict(filters=64, strides=[2, 2], blocks=2),
                    AttrDict(filters=128, strides=[2, 2], blocks=2),
                    #AttrDict(filters=256, strides=[2, 2], blocks=2),
                    #AttrDict(filters=512, strides=[2, 2], blocks=2),
                ],
                data_format=args.data_format
            ),
            num_classes=37,
            data_format=args.data_format,
            hyper_params=AttrDict(
                learning_rate=0.001,
                beta1=0.9,
                beta2=0.999
            )
        )(features, labels, mode),
        model_dir=args.model_dir,
        config=tf.estimator.RunConfig(
            tf_random_seed=args.random_seed,
            session_config=tf.ConfigProto(
                gpu_options=tf.GPUOptions(
                    visible_device_list=args.gpu,
                    allow_growth=True
                )
            )
        )
    )

    if args.train:

        classifier.train(
            input_fn=Dataset(
                filenames=args.filenames,
                num_epochs=args.num_epochs,
                batch_size=args.batch_size,
                sequence_lengths=[],
                image_size=[128, 128],
                data_format=args.data_format,
                encoding="png"
            ),
            steps=args.steps,
            max_steps=args.max_steps
        )

    if args.eval:

        eval_results = classifier.evaluate(
            input_fn=Dataset(
                filenames=args.filenames,
                num_epochs=1,
                batch_size=args.batch_size,
                sequence_lengths=[],
                image_size=[128, 128],
                data_format=args.data_format,
                encoding="png"
            )
        )

        print(eval_results)


if __name__ == "__main__":
    tf.app.run()
