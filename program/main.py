# -*- coding: utf-8 -*-

from __future__ import division

import argparse
import datetime
import pickle
from tqdm import tqdm

import numpy as np

from ReGNN import ReGNN
from utils import Data

parser = argparse.ArgumentParser()
parser.add_argument('--dataset', default='YoochooseSubDataset',
                    help='dataset name: diginetica/yoochoose1_4/yoochoose1_64/YoochooseSubDataset')
parser.add_argument('--method', type=str, default='ggnn', help='ggnn/gat/gcn')
parser.add_argument('--validation', action='store_true', help='validation')
parser.add_argument('--epoch', type=int, default=30, help='number of epochs to train for')
parser.add_argument('--batchSize', type=int, default=100, help='input batch size')
parser.add_argument('--hiddenSize', type=int, default=100, help='hidden state size')
parser.add_argument('--l2', type=float, default=1e-5, help='l2 penalty')
parser.add_argument('--lr', type=float, default=0.001, help='learning rate')
parser.add_argument('--step', type=int, default=1, help='gnn propogation steps')
parser.add_argument('--nonhybrid', action='store_true', help='global preference')
parser.add_argument('--lr_dc', type=float, default=0.1, help='learning rate decay rate')
parser.add_argument('--lr_dc_step', type=int, default=3, help='the number of steps after which the learning rate decay')
opt = parser.parse_args()
train_data = pickle.load(open('../datasets/' + opt.dataset + '/train.txt', 'rb'))
test_data = pickle.load(open('../datasets/' + opt.dataset + '/test.txt', 'rb'))
if opt.dataset == 'diginetica':
    n_node = 43098
elif opt.dataset == 'yoochoose1_64' or opt.dataset == 'yoochoose1_4' or opt.dataset == 'YoochooseSubDataset':
    n_node = 37484
else:
    n_node = 310

train_data = Data(train_data, sub_graph=True, method=opt.method, shuffle=True,
                  n_node=n_node - 1)
test_data = Data(test_data, sub_graph=True, method=opt.method, shuffle=False, n_node=n_node - 1)
model = ReGNN(hidden_size=opt.hiddenSize, out_size=opt.hiddenSize, batch_size=opt.batchSize, n_node=n_node,
              lr=opt.lr, l2=opt.l2, step=opt.step, decay=opt.lr_dc_step * len(train_data.inputs) / opt.batchSize,
              lr_dc=opt.lr_dc,
              nonhybrid=opt.nonhybrid)
print(opt)
best_result = [0, 0]
best_epoch = [0, 0]
p_20 = []
mrr_20 = []

for epoch in range(opt.epoch):
    print('epoch: ', epoch, '===========================================')
    slices = train_data.generate_batch(model.batch_size)
    fetches = [model.opt, model.loss_train, model.global_step]
    print('start training: ', datetime.datetime.now())
    loss_ = []
    for i, j in tqdm(zip(slices, np.arange(len(slices)))):
        adj_in, adj_out, alias, item, mask, targets, mask_r, mask_e = train_data.get_slice(
            i, n_node - 1)
        _, loss, _ = model.run(fetches, targets, item, adj_in, adj_out, alias, mask, mask_r, mask_e)
        loss_.append(loss)
    loss = np.mean(loss_)
    slices = test_data.generate_batch(model.batch_size)
    print('start predicting: ', datetime.datetime.now())
    hit, mrr, test_loss_ = [], [], []
    z = zip(slices, np.arange(len(slices)))
    for i, j in tqdm(zip(slices, np.arange(len(slices)))):
        adj_in, adj_out, alias, item, mask, targets, mask_r, mask_e = train_data.get_slice(
            i, n_node - 1)
        scores, test_loss = model.run([model.score_test, model.loss_test], targets, item, adj_in, adj_out, alias,
                                      mask, mask_r, mask_e)
        test_loss_.append(test_loss)
        index = np.argsort(scores, 1)[:, -20:]
        for score, target in zip(index, targets):
            hit.append(np.isin(target - 1, score))
            z0 = np.where(score == target - 1)
            z = np.where(score == target - 1)[0]
            if len(z) == 0:
                mrr.append(0)
            else:

                mrr.append(1 / (20 - np.where(score == target - 1)[0][0]))
    hit = np.mean(hit) * 100
    mrr = np.mean(mrr) * 100
    test_loss = np.mean(test_loss_)
    if hit >= best_result[0]:
        best_result[0] = hit
        best_epoch[0] = epoch
    if mrr >= best_result[1]:
        best_result[1] = mrr
        best_epoch[1] = epoch
    print('train_loss:\t%.4f\ttest_loss:\t%4f\tRecall@20:\t%.4f\tMMR@20:\t%.4f\tEpoch:\t%d,\t%d' %
          (loss, test_loss, best_result[0], best_result[1], best_epoch[0], best_epoch[1]))

