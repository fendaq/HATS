import tensorflow as tf
import numpy as np
import argparse
import glob
import os
from tqdm import *


parser = argparse.ArgumentParser()
parser.add_argument("--input_directory", type=str, default="train", help="input multi-mnist directory")
parser.add_argument("--output_filename", type=str, default="train.tfrecord", help="output tfrecord filename")
parser.add_argument("--sequence_length", type=int, default=5, help="number of digits contained in a instance (include blank)")
args = parser.parse_args()


def pad(sequence, sequence_length, value):
    while len(sequence) < sequence_length:
        sequence.append(value)
    return sequence


def main(input_directory, output_filename, sequence_length):

    with tf.python_io.TFRecordWriter(output_filename) as writer:

        for filename in glob.glob(os.path.join(input_directory, "*.jpg")):

            label = list(map(int, list(os.path.splitext(os.path.basename(filename))[0])))
            label = pad(label, sequence_length, 10)

            writer.write(
                record=tf.train.Example(
                    features=tf.train.Features(
                        feature={
                            "path": tf.train.Feature(
                                bytes_list=tf.train.BytesList(
                                    value=[filename.encode("utf-8")]
                                )
                            ),
                            "label": tf.train.Feature(
                                int64_list=tf.train.Int64List(
                                    value=label
                                )
                            )
                        }
                    )
                ).SerializeToString()
            )


if __name__ == "__main__":

    main(args.input_directory, args.output_filename, args.sequence_length)