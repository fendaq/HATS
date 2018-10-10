import tensorflow as tf
import argparse
import os
import glob

parser = argparse.ArgumentParser()
parser.add_argument("--filename", type=str, required=True, help="tfrecord filename")
parser.add_argument("--directory", type=str, required=True, help="path to data directory")
args = parser.parse_args()

with tf.python_io.TFRecordWriter(args.filename) as writer:

    for label, sub_directory in enumerate(glob.glob(os.path.join(args.directory, "*"))):

        for file in glob.glob(os.path.join(sub_directory, "*")):

            writer.write(
                record=tf.train.Example(
                    features=tf.train.Features(
                        feature={
                            "path": tf.train.Feature(
                                bytes_list=tf.train.BytesList(
                                    value=[file.encode("utf-8")]
                                )
                            ),
                            "label": tf.train.Feature(
                                int64_list=tf.train.Int64List(
                                    value=[label]
                                )
                            )
                        }
                    )
                ).SerializeToString()
            )
