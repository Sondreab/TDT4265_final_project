#!/usr/bin/env python
# coding: utf-8

# In[41]:
import numpy as np
import os
import cv2
from numpy.random import seed
seed(1)
from tensorflow import set_random_seed
set_random_seed(2)

from keras import optimizers
from keras import models
from keras.models import load_model, Sequential
from keras.layers import Dense, Flatten, Dropout, Convolution2D, Lambda, Cropping2D
from keras.preprocessing.image import img_to_array, load_img
from keras.callbacks import ModelCheckpoint
from keras.backend import tf
from matplotlib import pyplot as plt
from PIL import Image
#import innvestigate
 
flip_images = False
shade_images = False

def model(load, saved_model, shape=(66,200,3)):


    if load and saved_model: return load_model(saved_model, custom_objects={"tf": tf})
    

    model = Sequential()
    
    model.add(Lambda(lambda image: tf.image.resize_images(image, (66,200) ), input_shape=(75,320,3)))
    
    # 3 @ 66x200
    model.add(Convolution2D(filters=24, kernel_size=(5,5), strides=(2,2), 
                    data_format="channels_last", activation="relu"))
    # 24 @ 31x98
    model.add(Convolution2D(filters=36, kernel_size=(5,5), strides=(2,2), 
                    data_format="channels_last", activation="relu"))
    # 36 @ 14x47
    model.add(Convolution2D(filters=48, kernel_size=(5,5), strides=(2,2), 
                    data_format="channels_last", activation="relu"))
    # 48 @ 5x22
    model.add(Convolution2D(filters=64, kernel_size=(3,3), 
                    data_format="channels_last", activation="relu"))
    # 64 @ 3x20
    model.add(Convolution2D(filters=64, kernel_size=(3,3), 
                    data_format="channels_last", activation="relu"))
    # 64 @ 1x18
    model.add(Flatten()) # 1164 neurons

    model.add(Dense(100, activation="relu"))
    model.add(Dropout(0.5))
    model.add(Dense(50, activation="relu"))
    model.add(Dropout(0.5))
    model.add(Dense(10, activation="linear"))

    model.add(Dense(1, activation="tanh"))
    
    optim = optimizers.Adam(lr=10e-4)
    model.compile(loss="mse", optimizer=optim)

    return model

def visualization_model(model, img_tensor):

    path = os.getcwd().split(os.sep)[:-1]
    path = path + ['docs'] + ['plots']
    path = (os.sep).join(path)

    os.makedirs(path, exist_ok=True) #location of the plots
    layer_outputs = [layer.output for layer in model.layers[:]]
    activation_model = models.Model(inputs=model.input, outputs=layer_outputs)

    activations = activation_model.predict(img_tensor)

    #Special case for the first image
    img = activations[0][0, :, :, :]
    print(img.shape)
    rgb_img = cv2.cvtColor(img, cv2.COLOR_HSV2RGB)
    fig = plt.figure()
    plt.imshow(rgb_img) 
    fig.savefig(path + os.sep + "first_layer")


    layer_names = []
    #Visualizing the conv layers:
    for layer in model.layers[1:6]:
        layer_names.append(layer.name)

    #change these to change the number of channels to visualize
    col_size=5
    row_size=5

    
    for layer_name, layer_activation in zip(layer_names, activations[0:]):
        print(layer_activation.shape)
        print(layer_name)

        act_idx = 0
        fig, ax = plt.subplots(row_size, col_size, figsize=(row_size*2.5,col_size*1.5))
        fig.suptitle(layer_name)
        for col in range(0,col_size):
            for row in range(0,row_size):
                if (act_idx >= layer_activation.shape[3]):
                    break
                ax[row][col].imshow(layer_activation[0, :, :, act_idx], cmap='viridis')
                act_idx +=1
        
        
        #plt.show()
        fig.savefig(path + os.sep + layer_name)
        
# load image into known format.

def image_handling(path, steering_angle, shape):
    """ Image handling 
        Will load in the images listed in the supplied .csv file and do augmentation if
        flags for it is set. Flags are set in top of this file.
    
    """
    image = Image.open(path)
    image_array = np.asarray(image)
    image_array = image_array[65:len(image_array)-20, :, :]
    image_array = image_array[...,::-1]

    #flip 50% og the images
    if ((np.random.random() < 0.5) and flip_images):
        image_array = image_array[:,::-1,:]
        steering_angle = -steering_angle

    if np.random.random() < 0.5:
        image_array = image_array[:,::-1,:] #flip_axis(image_array, 1)
        steering_angle = -steering_angle

    #To HSV; same as drive.py
    img = cv2.cvtColor(np.array(image_array), cv2.COLOR_BGR2HSV)

    # shade 20% of the images
    if ((np.random.random() < 0.2) and shade_images):
        x_vertices = [round(np.random.random()*img.shape[1]), round(np.random.random()*img.shape[1])]
        x_min = min(min(x_vertices), 250)
        x_max = max(max(x_vertices), x_min + 70)
        y_vertices = [round(np.random.random()*img.shape[0]), round(np.random.random()*img.shape[0])]
        y_min = min(min(y_vertices), 55)
        y_max = max(max(y_vertices), y_min + 20)
        shade_scale = np.random.random()
        for y in range(y_min, y_max):
            for x in range(x_min, x_max):
                img[y,x,2] = min(round(img[y,x,2]*shade_scale), 100)

    #Normalize pixels
    img = (img/255)-0.5

    return img, steering_angle

def split_data(nr_pts):
    """
    Split dataset into training and validation sets
    """
    idx = np.arange(nr_pts)
    np.random.shuffle(idx)
    
    tr = int(np.floor(nr_pts*0.8))
    train    = idx[:tr]
    validate = idx[tr:]
    return train, validate

def sample_idx(batch_size, y, proportion):
    '''
    Sampling indices for data, skewing to ensure lower percentage of straights.
    '''

    i    = 0
    idx  = [0]*batch_size
    data_num = len(y)
    while i < batch_size:
        candidate = np.random.randint(0,data_num,1)[0]
        #Image of driving forward
        if abs(y[candidate]) <= 0.05 and np.random.ranf(1) < (1-proportion)*0.33:
            idx[i] = candidate
            i+=1
        #Image of turning
        elif abs(y[candidate]) > 0.05 and np.random.ranf(1) < proportion:
            idx[i]  = candidate
            i+=1
    return idx


def _generator(batch_size, X, y, shape, path, proportion):
    """
    Generator for data batches to avoid flooding RAM with the whole dataset
    """
    while True:
        batch_x   = []
        batch_y   = []
        idx = sample_idx(batch_size, y, proportion) 
        for i in idx:
            x, angle = image_handling(path + os.sep + X[i], y[i], shape)
            batch_x.append(x)
            batch_y.append(angle)

        yield np.array(batch_x), np.array(batch_y)
              
def load_data(path, log, shape, load=False, saved_model=None):
    '''Function wrapper for loading and splitting data OR loading model.'''
    front, left, right = np.loadtxt(log, delimiter=",", usecols=[0,1,2], dtype="str", unpack=True)
    angle, forward, backward, speed = np.loadtxt(log, delimiter=",", usecols=[3,4,5,6], unpack=True)
    
    #Proportion of roughly straight forward images
    proportion = np.sum(abs(angle) <= 0.05)/float(len(angle))
    #Splitting into training and validation sets, to be sampled in generators
    train, validate = split_data(len(front))
    X, y = front[train], angle[train]
    X_val, y_val = front[validate], angle[validate]
    
    net = model(load, saved_model=saved_model, shape=shape)

    return net, X, y, X_val, y_val, proportion

def save_loss_plot(history):
    '''Saving plot of loss during training of model'''
    fig = plt.figure()
    l = plt.plot(history.history["loss"])
    v = plt.plot(history.history["val_loss"])
    plt.xlabel("Epoch")
    plt.ylabel("Loss")
    plt.legend((l, v), ('training', 'validation'))
    plt.title("Loss v epoch")
    fig.savefig("loss.jpg")
    
def activation_mapping(img_path, log, shape, load=False, saved_model=None, num_maps=5):
    '''Not applicable for models with lambda layers, hence can only be used on no_lambda_model.h5 of those supplies.'''
    seed(697)
    _, X, y, X_val, y_val, proportion = load_data(path,log)
    
    idx_train = sample_idx(2000, y, proportion) 
    X_train = np.zeros((2000,)+shape)
    names_train   = []
    for i, idx in enumerate(idx_train):
        img, _ = image_handling(img_path + os.sep + X[idx], 0, shape)
        X_train[i] = img
        names_train.append(X[idx])
        
    idx_test = sample_idx(num_maps, y_val, proportion) 
    X_test = np.zeros((num_maps,)+shape)
    names_test   = []
    for i, idx in enumerate(idx_test):
        img, _ = image_handling(img_path + os.sep + X[idx], 0, shape)
        X_test[i] = img
        names_test.append(X[idx])

    trained_model = model(load=True, saved_model=saved_model, shape=0) if load else saved_model
    analyzer = innvestigate.create_analyzer("pattern.net", trained_model)
    analyzer.fit(X_train)
    a = analyzer.analyze(X_test)
    a = np.abs(a.sum(axis=np.argmax(np.asarray(a.shape) == 3)))
    
    def transparent_cmap(cmap, N=255):
        "Copy colormap and set alpha values"

        mycmap = cmap
        mycmap._init()
        mycmap._lut[:,-1] = np.linspace(0, 0.8, N+4)
        return mycmap

    mycmap = transparent_cmap(plt.cm.Reds)
    for i in np.arange(num_maps):
        
        x, angle = image_handling(img_path + os.sep + names_test[i],
                                  0, shape=shape)
        image = Image.open(img_path + os.sep + names_test[i])
        image_array = np.asarray(image)
        image_array = image_array[65:len(image_array)-20, :, :]
        image_array = image_array[...,::-1]

        fig1, ax1 = plt.subplots()
        ax1.imshow(image_array)
        cs = ax1.contourf(a[i], cmap = mycmap, levels=30)
        fig1.colorbar(cs)
        fig1.savefig("activation" + str(i) + ".jpg")
        plt.close()
    
    
def train(path,log):

    load_pretrained_model = False
    saved_model = 'model_trained_both.h5'

    shape = (75,320,3)
    # Load data from csv
    front, left, right = np.loadtxt(log, delimiter=",", usecols=[0,1,2], dtype="str", unpack=True)
    angle, forward, backward, speed = np.loadtxt(log, delimiter=",", usecols=[3,4,5,6], unpack=True)


    proportion = np.sum(abs(angle) <= 0.05)/float(len(angle))
    print('prop: ', proportion)
    train, validate = split_data(len(front))
    net = model(load=load_pretrained_model, saved_model=saved_model, shape=shape)
    X, y = front[train], angle[train]

    # Showing how many datapoints within each interval of steering angle
    fig = plt.figure()
    plt.hist(y, bins=[-1.1, -0.8, -0.5, -0.2,  -0.05, 0.05, 0.2, 0.5, 0.8, 1.1])
    fig.savefig('training_data_histogram')

    X_val, y_val = front[validate], angle[validate]
    
    #Saving the best epoch
    checkpoint = ModelCheckpoint('model.h5', monitor='val_loss', verbose=1, save_best_only=True)

    net.summary()

    if not load_pretrained_model:
        history = net.fit_generator(generator = _generator(64, X, y, shape, path, proportion),
                        validation_data  = _generator(20, X_val, y_val, shape, path, proportion),
                        validation_steps = 20, 
                        epochs = 50, steps_per_epoch=50,
                        callbacks=[checkpoint])
        save_loss_plot(history)
    
    
    #Manual check of predictions
    test_idx = sample_idx(50, y, proportion) 
    for i in test_idx:
        img, _ = image_handling(img_path + os.sep + X[i], 0, shape)
        img = np.reshape(img, (1,) + shape)
        pred = net.predict(img)
        print("Pred: ", pred, " True: ", y[i])
    
    #Visualization of learned patterns
    img_vis, _ = image_handling(img_path + os.sep + X[1], 0, shape)
    img_vis = np.reshape(img_vis, (1,) + shape)
    #visualization_model(net, img_vis)
    
    #activation_mapping(img_path, log, shape, load=False, model=net)
    
    return net
 

if __name__ == "__main__":
    path = os.getcwd().split(os.sep)[:-1]
    log = (os.sep).join(path + ["driving_log_both.csv"]) ## Path to csv file containing info on pictures used in training data
    img_path = (os.sep).join(path + ["IMG_both"]) ## Path to images listed in csv file.
        
    
    net = train(img_path, log)
    #activation_mapping(img_path=(os.sep).join(path + ["IMG_track2"]) , log=(os.sep).join(path + ["driving_log_track2.csv"]), shape=(75,320,3), load=True, saved_model='no_lambda_model.h5')
