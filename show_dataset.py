import tensorflow as tf
import cv2
import sys

class_ids = {}
class_ids.update({chr(j): i for i, j in enumerate(range(ord("0"), ord("9") + 1), 0)})
class_ids.update({chr(j): i for i, j in enumerate(range(ord("A"), ord("Z") + 1), class_ids["9"] + 1)})
class_ids.update({"": max(class_ids.values()) + 1})
class_names = dict(map(lambda x: x[::-1], class_ids.items()))

for record in tf.python_io.tf_record_iterator(sys.argv[1]):

    example = tf.train.Example()
    example.ParseFromString(record)

    path = example.features.feature["path"].bytes_list.value[0].decode()
    label = "".join(list(map(lambda class_id: class_names[class_id], example.features.feature["label"].bytes_list.value)))

    print(example.features.feature["label"].bytes_list.value)
    cv2.imshow("image", cv2.imread(path))

    if cv2.waitKey() == ord("q"):
        break
