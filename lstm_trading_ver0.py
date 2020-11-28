# -*- coding: utf-8 -*-
"""lstm_trading_W7.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/19N3PjvbrBNWzwnp9OeAYoJTvTf94kxvX
"""

import pkg_resources
pkg_resources.get_distribution("keras").version

from google.colab import drive
drive.mount('/content/drive')

# Commented out IPython magic to ensure Python compatibility.
# %tensorflow_version 1.x 

import pandas as pd
from sklearn import preprocessing
from sklearn.metrics import classification_report, confusion_matrix
from collections import deque
import random
import numpy as np
import pandas_datareader as pdr
from datetime import datetime,date
import keras
from keras.models import Sequential,load_model
from keras.layers import Dense, Dropout, LSTM, CuDNNLSTM, BatchNormalization
from keras.callbacks import TensorBoard, ModelCheckpoint
import time
import collections
import matplotlib.pyplot as plt
from tqdm import tnrange, tqdm_notebook
pd.options.mode.chained_assignment = None
from keras_self_attention import SeqSelfAttention



def log(s, *args, **kwargs):
    timestamp = "{:%H:%M:%S.%f}".format(datetime.now())[:-3]
    print(timestamp, s.format(*args, **kwargs))

def cal_px_mid(px_bid,px_ask):
    px_mid=(px_bid+px_ask)/2
    return px_mid

def cal_px_return(px,window=60):
    px_return=np.log(px/px.shift(periods=window))
    return px_return

def cal_rolling_std(data,rolling=600):
    rolling_std=data.rolling(window=rolling).std()
    return rolling_std

def random_adj():
    return np.random.randint(low=-10, high=10)/100+1

random_lambda = lambda i: random_adj()*i
vectorized_random_adj=np.vectorize(random_lambda)


def preprocess_df(df,process_type):
    SEQ_LEN=600 #Last X days price to predict
    FUTURE_PERIOD_PREDICT=60 #Next X days price
    EPOCHS=100
    BATCH_SIZE=64

    if process_type == 'test':
       df['target']=df['momentum_0.1%*std_60s'] 
    elif process_type=='validation':
        df['target']=df['momentum_0.1%*std_60s'] 
    
    df.loc[df['target']==1,'target']=1
    df.loc[df['target']==0,'target']=2
    df.loc[df['target']==-1,'target']=0

    df['px_mid']=cal_px_mid(df['px_bid'],df['px_ask'])
    df['return_10m']=cal_px_return(df['px_mid'],window=600)
    df['return_30m']=cal_px_return(df['px_mid'],window=1800)
    df['stdev_30m']=cal_rolling_std(df['return_10m'],rolling=1800)
    df['size_support']=np.log(df['bid_size_total']/df['ask_size_total'])

    df=df[['return_10m','return_30m','stdev_30m','size_support','ls_amount','target']]


    for col in df.columns:
        if col != "target":
            df.fillna(0,inplace=True) 
            df.loc[:,col]=preprocessing.scale(df[col].values)



    sequential_data = []
    prev_days=deque(maxlen=SEQ_LEN)
    
    for i in tqdm_notebook(df.values):
        prev_days.append([n for n in i[:-1]])

        if len(prev_days) == SEQ_LEN:
            sequential_data.append([np.array(prev_days),i[-1]])

    log('3d array generated')             

    df_min=pd.DataFrame(np.array(sequential_data)[:,1])
    lower= min(min(df_min.loc[:,0].value_counts()),5000) 
    log(f'lower is: {lower}')
    
    log('3 category') 
    class_long=[]
    class_none=[]
    class_short=[]
    
    sequential_data=np.array(sequential_data)

    class_long=list(zip(sequential_data[sequential_data[:,1]==1][:,0],sequential_data[sequential_data[:,1]==1][:,1]))
    class_none=list(zip(sequential_data[sequential_data[:,1]==2][:,0],sequential_data[sequential_data[:,1]==2][:,1]))
    class_short=list(zip(sequential_data[sequential_data[:,1]==0][:,0],sequential_data[sequential_data[:,1]==0][:,1]))
    
    log('apply lower')    
    class_long=class_long[:lower]
    class_none=class_none[:lower]
    class_short=class_short[:lower]  

    sequential_data=np.array(list(class_long)+list(class_none)+list(class_short))
    np.random.shuffle(sequential_data)

    log('seq generated') 
    x=sequential_data[:,0]
    x=np.concatenate(x, axis=0)   
    x=x.reshape(int(x.shape[0]/600),600,5)
    y=sequential_data[:,1]
    log('x,y generated') 

    return x,y

def preprocess_test_df(df):
    SEQ_LEN=600 #Last X days price to predict
    FUTURE_PERIOD_PREDICT=60 #Next X days price
    EPOCHS=100
    BATCH_SIZE=64 


    df['target']=df['momentum_0.1%*std_60s']   

    df['px_mid']=cal_px_mid(df['px_bid'],df['px_ask'])
    df['return_10m']=cal_px_return(df['px_mid'],window=600)
    df['return_30m']=cal_px_return(df['px_mid'],window=1800)
    df['stdev_30m']=cal_rolling_std(df['return_10m'],rolling=1800)
    df['size_support']=np.log(df['bid_size_total']/df['ask_size_total'])
    #data['ls_amount_sum']=data['ls_amount'].rolling(window=60).sum()

    df=df[['return_10m','return_30m','stdev_30m','size_support','ls_amount','target']]


    for col in df.columns:
        if col != "target":
            #df[col]=df[col].pct_change() #Percentage change between the current and a prior element.
            df.fillna(0,inplace=True)
            df.loc[:,col]=preprocessing.scale(df[col].values)

    sequential_data = []
    prev_days=deque(maxlen=SEQ_LEN)

    # print('in function df shape:')
    # print(len(df.values))

    for i in tqdm_notebook(df.values):
        prev_days.append([n for n in i[:-1]])
        if len(prev_days) == SEQ_LEN:
            sequential_data.append([np.array(prev_days),i[-1]])
    
    #  x,y=[],[]
    #  for seq, target in sequential_data:
    #      X.append(seq)
    #      y.append(target)
    # random.shuffle(sequential_data)#for good measure
    sequential_data=np.array(sequential_data)
    log('seq generated') 
    x=sequential_data[:,0]
    x=np.concatenate(x, axis=0)
    x=x.reshape(int(x.shape[0]/600),600,5)
    y=sequential_data[:,1]
    log('x,y generated') 

    return x, y

"""# Model Training"""

from keras.layers import Embedding



def create_model(train_x):
    model=Sequential()
    model.add(CuDNNLSTM(32, input_shape=(train_x.shape[1:]), return_sequences=True))
    model.add(Dropout(0.2))
    model.add(BatchNormalization())

    model.add(CuDNNLSTM(64, return_sequences=True))
    model.add(Dropout(0.2))
    model.add(BatchNormalization())

    model.add(CuDNNLSTM(32))
    model.add(Dropout(0.3))
    #model.add(BatchNormalization())

    
    # lstm_section = Dense(1,activation='sigmoid')
    # attention=Dense(1, activation='tanh')( lstm_section )
    # attention=Flatten()( attention )
    # attention=Activation('softmax')( attention )
    # attention=RepeatVector(64)( attention )
    # attention=Permute([2, 1])( attention )

    model.add(SeqSelfAttention(attention_activation='sigmoid'))


    #model.add(Dense(32, activation = attention))
    model.add(Dense(32, activation="relu"))
    model.add(Dropout(0.2))
    model.add(Dense(3, activation="softmax"))
    #model.add(Activation('softmax'))

    
    return model

def train_model(x_train,y_train,x_validation,y_validation,date_mark):

    from keras.optimizers import SGD

    ###model = load_model('LSTM_test_v1.hdf5')

    SEQ_LEN=600 #Last X days price to predict
    FUTURE_PERIOD_PREDICT=60 #Next X days price
    EPOCHS=50
    BATCH_SIZE=64
    NAME=f"{SEQ_LEN}-SEQ-{FUTURE_PERIOD_PREDICT}-PRED-{int(time.time())}"

    model=create_model(x_train) #这里call里之前的function
    
    sgd = SGD(lr=0.0001, decay=1e-6, momentum=0.9, nesterov=True)#model的optimizer,之前sample用的atom这里用的SGD。 SGD比较老，效果可能差一点
    #

    model.compile(loss = "sparse_categorical_crossentropy", 
                  optimizer = sgd, 
                  metrics=['accuracy']
                )

    tensorboard=TensorBoard(log_dir=f'logs/{NAME}')
    filepath=f"LSTM_test_{date_mark}-3"
    checkpoint=ModelCheckpoint("/content/drive/My Drive/Colab Notebooks/{}.hdf5".format(filepath, monitor='val_acc', verbose=1, save_best_only=True, mode='max'))

    history=model.fit(x_train,y_train,batch_size=BATCH_SIZE,validation_data=(x_validation,y_validation),epochs=EPOCHS, callbacks=[tensorboard,checkpoint])

DATE_MASK_LIST = ['20191104','20191105']#,'20191103'] #,'20191106','20191107','20191108','20191109']


df_dic={}
for DATE_MASK in DATE_MASK_LIST:
    df=pd.read_csv(f'/content/drive/My Drive/bit11/{DATE_MASK}_market_data_with_label_v3.csv') #这里因为只有一个文件改了下路径，文件多的时候再单独创文件夹
    df.fillna(0,inplace=True)
    df_dic.update({DATE_MASK:df}) #df_dic是 dictionary,key-value pair,


df_set=pd.DataFrame()
df_set=pd.concat([df_dic[DATE_MASK].copy() for DATE_MASK in DATE_MASK_LIST]) 
df_train=df_set
log('preprocess start')
x_train,y_train=preprocess_df(df_train,process_type='test')
log('preprocess end')

y_train

DATE_MASK_LIST = ['20191106']#,'20191104'] #'20191105'] #,'20191106','20191107','20191108','20191109']
 df_dic={}
 for DATE_MASK in DATE_MASK_LIST:
     df=pd.read_csv(f'/content/drive/My Drive/bit11/{DATE_MASK}_market_data_with_label_v3.csv')
     df.fillna(0,inplace=True)
     df_dic.update({DATE_MASK:df})
     log(f'{DATE_MASK} validation loaded')
    
 df_validation=pd.DataFrame()

 df_validation=pd.concat([df_dic[DATE_MASK].copy() for DATE_MASK in DATE_MASK_LIST])  
# df_validation=df_validation[60000:]
# df_validation = df_set[60000:]
log('preprocess start') 
x_validation,y_validation=preprocess_df(df_validation,process_type='validation')
log('preprocess end')

date_mark=DATE_MASK_LIST[-1]
train_model(x_train,y_train,x_validation,y_validation,date_mark)


from keras.models import load_model
model = load_model('/content/drive/My Drive/Colab Notebooks/LSTM_test_20191104-3.hdf5')

DATE_MASK_LIST = ['20191106']#,'20191108']#,'20191108']#,'20191109']
#DATE_MASK_LIST = ['20191112','20191113','20191114','20191115']
df_dic={}
for DATE_MASK in DATE_MASK_LIST:
    df=pd.read_csv(f'/content/drive/My Drive/bit11/{DATE_MASK}_market_data_with_label_v3.csv')
    df.fillna(0,inplace=True)
    df_dic.update({DATE_MASK:df})
    
df_test_all=pd.DataFrame()
df_test_all=pd.concat([df_dic[DATE_MASK].copy() for DATE_MASK in DATE_MASK_LIST])  

#test_df=pd.read_excel("20191105_2_factor_momentum.xlsx")


#prediction
print(df_test_all.shape)
print('test df loaded')
X_test,Y_true=preprocess_df(df_test_all,process_type='test')
print(len(X_test))
print('X_test prepared')
output_prob=model.predict_proba(x_validation,verbose=1)
print('output prob generated')

predict = model.predict_classes(X_test)

output_prob

predict

Y_true = Y_true.astype(int)

confusion_matrix(Y_true,predict)

from sklearn.metrics import accuracy_score 
accuracy_score(Y_true, predict)

thre = 0.8
output_save = []

for i in range(len(output_prob)):
  if max(output_prob[i]) > thre:
    output_save.append([predict[i], Y_true[i]])
  else:
    continue

output_save

len(output_save)/len(predict)

output_save = np.array(output_save)
accuracy_score(output_save[:, 0], output_save[:, 1])

confusion_matrix(output_save[:, 0], output_save[:, 1])