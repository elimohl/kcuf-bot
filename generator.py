#!/usr/bin/env python3

from keras.models import Sequential
from keras.layers.core import Dense, Activation, Dropout
from keras.layers.recurrent import LSTM
from keras.models import model_from_json
import numpy as np
import random


text = open("corpus.txt").read().lower()
print('corpus length:', len(text))

chars = set(text)
print('total chars:', len(chars))
char_indices = dict((c, i) for i, c in enumerate(chars))
indices_char = dict((i, c) for i, c in enumerate(chars))

maxlen = 20
step = 3


def sample(a, temperature=1.0):
    # helper function to sample an index from a probability array
    a = np.log(a) / temperature
    a = np.exp(a) / np.sum(np.exp(a))
    return np.argmax(np.random.multinomial(1, a, 1))


def generate_reply(msg, diversity=1.):
    model = model_from_json(open('model_architecture.json').read())
    model.load_weights('model_weights.h5')

    print('----- diversity:', diversity)

    sentence = msg
    print('----- Generating with seed: "' + msg + '"')

    ans = ''
    while (ans[-2:] != '\n\n' and len(ans) < 1000):
        x = np.zeros((1, maxlen, len(chars)))
        for t, char in enumerate(sentence):
            x[0, t, char_indices[char]] = 1.

        preds = model.predict(x, verbose=0)[0]
        next_index = sample(preds, diversity)
        next_char = indices_char[next_index]

        ans += next_char
        sentence = sentence[1:] + next_char

    return ans


if __name__ == '__main__':
    sentences = []
    next_chars = []
    # cut the text in semi-redundant sequences of maxlen characters
    for i in range(0, len(text) - maxlen, step):
        sentences.append(text[i: i + maxlen])
        next_chars.append(text[i + maxlen])
    print('nb sequences:', len(sentences))

    print('Vectorization...')
    X = np.zeros((len(sentences), maxlen, len(chars)), dtype=np.bool)
    y = np.zeros((len(sentences), len(chars)), dtype=np.bool)
    for i, sentence in enumerate(sentences):
        for t, char in enumerate(sentence):
            X[i, t, char_indices[char]] = 1
        y[i, char_indices[next_chars[i]]] = 1

    # build the model: 2 stacked LSTM
    print('Build model...')
    model = Sequential()
    model.add(LSTM(512, return_sequences=True, input_shape=(maxlen, len(chars))))
    model.add(Dropout(0.2))
    model.add(LSTM(512, return_sequences=False))
    model.add(Dropout(0.2))
    model.add(Dense(len(chars)))
    model.add(Activation('softmax'))

    model.compile(loss='categorical_crossentropy', optimizer='rmsprop')
    json_string = model.to_json()
    open('model_architecture.json', 'w').write(json_string)

    # train the model, output generated text after each iteration
    for iteration in range(1, 60):
        print()
        print('-' * 50)
        print('Iteration', iteration)
        model.fit(X, y, batch_size=128, nb_epoch=1)

        start_index = random.randint(0, len(text) - maxlen - 1)
        model.save_weights('model_weights.h5', overwrite=True)
