# -*- coding: utf-8 -*-
# Author: XuMing <xuming624@qq.com>
# Brief: 
from math import log

import xgboost as xgb

N = 4000


def get_word_set(segment_text):
    word_list = segment_text.split()
    word_set = set(word_list)
    return word_list, word_set


def process_file(train_path):
    '''
    本函数用于处理样本集中的所有文件。并返回处理结果所得到的变量
    :param floder_path: 样本集路径
    :return: A：CHI公示中的A值，嵌套字典。用于记录某一类中包含单词t的文档总数。第一层总共9个key，对应9类新闻分类
                第二层则是某一类中所有单词及其包含该单词的文档数（而不是出现次数）。{{1：{‘hello’：8，‘hai’：7}}，{2：{‘apple’：8}}}
            TFIDF：用于计算TFIDF权值。三层嵌套字典。第一层和A一样，key为类别。第二层的key为文件名（这里使用文件编号代替0-99）.第三层
                    key为单词，value为盖单词在本文件中出现的次数。用于记录每个单词在每个文件中出现的次数。
            data_content:训练样本集。与测试样本集按7:3比例分开。三元组（文档的单词表，类别，文件编号）
            test_set:测试样本集。三元组（文档的单词表，类别，文件编号）
    '''
    # 用于记录CHI公示中的A值
    A = {}
    tf = []
    i = 0
    # 存储训练集/测试集
    count = [0] * 2
    train_set = []
    train_label = []
    import os
    if not os.path.exists(train_path):
        print('file not exists.')
        return
    with open(train_path, 'r', encoding='utf-8') as f:
        for line in f:
            tf.append({})
            parts = line.strip().split('\t')
            label = 0 if parts[0].strip() == 'disapprove' else 1
            if label not in A:
                A[label] = {}
            count[label] += 1
            content = parts[1].strip()
            word_list, word_set = get_word_set(content)
            train_set.append((word_list, label))
            train_label.append(label)
            for word in word_set:
                if word in A[label]:
                    A[label][word] += 1
                else:
                    A[label][word] = 1
            for word in word_list:
                if word in tf[i]:
                    tf[i][word] += 1
                else:
                    tf[i][word] = 1
            i += 1
        print("处理完数据")
    return A, tf, train_set, count, train_label


def calculate_B_from_A(A):
    '''
    :param A: CHI公式中的A值
    :return: B，CHI公职中的B值。不是某一类但是也包含单词t的文档。
    '''
    B = {}
    for key in A:
        B[key] = {}
        for word in A[key]:
            B[key][word] = 0
            for kk in A:
                if kk != key and word in A[kk]:
                    B[key][word] += A[kk][word]
    return B


def feature_select_use_new_CHI(A, B, count):
    '''
    根据A，B，C，D和CHI计算公式来计算所有单词的CHI值，以此作为特征选择的依据。
    CHI公式：chi = N*（AD-BC）^2/((A+C)*(B+D)*(A+B)*(C+D))其中N,(A+C),(B+D)都是常数可以省去。
    :param A:
    :param B:
    :return: 返回选择出的1000多维特征列表。
    '''
    word_dict = []
    word_features = []
    for i in range(0, 2):
        CHI = {}

        M = N - count[i]
        for word in A[i]:
            # print word, A[i][word], B[i][word]
            temp = (A[i][word] * (M - B[i][word]) - (count[i] - A[i][word]) * B[i][word]) ** 2 / ( \
                (A[i][word] + B[i][word]) * (N - A[i][word] - B[i][word]))
            CHI[word] = log(N / (A[i][word] + B[i][word])) * temp
        # 每一类新闻中只选出150个CHI最大的单词作为特征
        a = sorted(CHI.items(), key=lambda t: t[1], reverse=True)[:300]
        b = []
        for aa in a:
            b.append(aa[0])
        word_dict.extend(b)
        for word in word_dict:
            if word not in word_features:
                word_features.append(word)
    return word_features


def document_features(word_features, TF, data, num):
    '''
    计算每一篇新闻的特征向量权重。即将文件从分词列表转化为分类器可以识别的特征向量输入。
    :param word_features:
    :param TFIDF:
    :param document: 分词列表。存储在train_set,test_set中
    :param cla: 类别
    :param num: 文件编号
    :return: 返回该文件的特征向量权重
    '''
    document_words = set(data)
    features = []
    for i, word in enumerate(word_features):
        if word in document_words:
            features.append(1)  # TF[num][word]#*log(N/(A[cla][word]+B[cla][word]))
        else:
            features.append(0)
    return features


A, tf, train_set, count, train_label = process_file('../data/risk/data_seg.txt')
B = calculate_B_from_A(A)
print("开始选择特征词")
word_features = feature_select_use_new_CHI(A, B, count)
print(word_features)
print(len(word_features))
for word in word_features:
    print(word)

print("开始计算文档的特征向量")
documents_feature = [document_features(word_features, tf, data[0], i)
                     for i, data in enumerate(train_set)]

# json.dump(documents_feature, open('tmp/documents_feature.txt', 'w'))
# json.dump(test_documents_feature, open('tmp/test_documents_feature.txt', 'w'))
#
dtrain = xgb.DMatrix(documents_feature, label=train_label)
# dtest = xgb.DMatrix(test_documents_feature)  # label可以不要，此处需要是为了测试效果
param = {'max_depth': 6, 'eta': 0.5, 'eval_metric': 'merror', 'silent': 1, 'objective': 'multi:softmax',
         'num_class': 11}  # 参数
evallist = [(dtrain, 'train')]  # 这步可以不要，用于测试效果
num_round = 100  # 循环次数
bst = xgb.train(param, dtrain, num_round, evallist)
# preds = bst.predict(dtest)
# with open('XGBOOST_CHI_OUTPUT.csv', 'w') as f:
#     for i, pre in enumerate(preds):
#         f.write(str(i + 1))
#         f.write(',')
#         f.write(str(int(pre) + 1))
#         f.write('\n')
