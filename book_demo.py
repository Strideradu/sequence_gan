from __future__ import print_function

import codecs

__doc__ = """Char-based Seq-GAN on data from a book."""

import model
import train

import os.path
import numpy as np
import tensorflow as tf
import random
import subprocess
import gzip

EMB_DIM = 32
HIDDEN_DIM = 32
SEQ_LENGTH = 12
START_TOKEN = 0

EPOCH_ITER = 1000
CURRICULUM_RATE = 0.005  # how quickly to move from supervised training to unsupervised
TRAIN_ITER = 200000  # generator/discriminator alternating
D_STEPS = 3  # how many times to train the discriminator per generator step
SEED = 88

DATA_FILE = 'wuyan.txt'


def tokenize(s):
    # return [c for c in ' '.join(s.split())]
    return list(s)


def get_data(download=not os.path.exists(DATA_FILE)):
    """Downloads and parses Moby Dick."""
    """
    if download:
        subprocess.check_output(
            ['wget', 'http://www.gutenberg.org/cache/epub/2701/pg2701.txt',
             '-O', DATA_FILE])

    """
    token_stream = []
    token = []
    is_gzip = False
    
    try:
        open(DATA_FILE, encoding="utf8").read(2)
    except UnicodeDecodeError:
        is_gzip = True
    with gzip.open(DATA_FILE) if is_gzip else codecs.open(DATA_FILE, 'r', 'utf-8') as f:
        for line in f:
            line = line if not is_gzip else line.decode('utf-8')
            if ('四时运灰琯' in line or token_stream) and line.strip():
                line_sp = line.strip().lower().split("。")
                for poem in line_sp:
                    token_stream.append(poem + "。")
                token.extend(line.strip().lower())
                #token_stream.append(' ')
            if len(token_stream) > 100000 * SEQ_LENGTH:  # enough data
                break

    return token_stream, token


class BookGRU(model.GRU):

    def d_optimizer(self, *args, **kwargs):
        return tf.train.AdamOptimizer()  # ignore learning rate

    def g_optimizer(self, *args, **kwargs):
        return tf.train.AdamOptimizer()  # ignore learning rate


def get_trainable_model(num_emb):
    return BookGRU(
        num_emb, EMB_DIM, HIDDEN_DIM,
        SEQ_LENGTH, START_TOKEN)


def get_random_sequence(token_stream, word2idx):
    """Returns random subsequence."""
    start_idx = random.randint(0, len(token_stream))
    chosen_token = token_stream[start_idx]
    if len(chosen_token) >= SEQ_LENGTH:
        chosen_token = chosen_token[0:SEQ_LENGTH]
    else:
        chosen_token = chosen_token + (SEQ_LENGTH - len(chosen_token)) * " "
    #return [word2idx[tok] for tok in token_stream[start_idx:start_idx + SEQ_LENGTH]]
    return [word2idx[tok] for tok in chosen_token]


def verify_sequence(three_grams, seq):
    """Not a true verification; only checks 3-grams."""
    for i in range(len(seq) - 3):
        if tuple(seq[i:i + 3]) not in three_grams:
            return False
    return True


def main():
    random.seed(SEED)
    np.random.seed(SEED)

    token_stream, token = get_data()
    assert START_TOKEN == 0
    words = ['_START'] + list(set(token))
    word2idx = dict((word, i) for i, word in enumerate(words))
    num_words = len(words)
    three_grams = dict((tuple(word2idx[w] for w in token[i:i + 3]), True)
                       for i in range(len(token) - 3))
    print('num words', num_words)
    print('stream length', len(token))
    print('distinct 3-grams', len(three_grams))

    trainable_model = get_trainable_model(num_words)
    sess = tf.Session()
    sess.run(tf.global_variables_initializer())

    print('training')
    for epoch in range(TRAIN_ITER // EPOCH_ITER):
        print('epoch', epoch)
        proportion_supervised = max(0.0, 1.0 - CURRICULUM_RATE * epoch)
        train.train_epoch(
            sess, trainable_model, EPOCH_ITER,
            proportion_supervised=proportion_supervised,
            g_steps=1, d_steps=D_STEPS,
            next_sequence=lambda: get_random_sequence(token_stream, word2idx),
            verify_sequence=lambda seq: verify_sequence(three_grams, seq),
            words=words)


if __name__ == '__main__':
    main()
