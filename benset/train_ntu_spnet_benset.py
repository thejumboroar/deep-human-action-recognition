import os
import sys

#if os.path.realpath(os.getcwd()) != os.path.dirname(os.path.realpath(__file__)):
#    sys.path.append(os.getcwd())

import deephar

from deephar.config import mpii_dataconf
from deephar.config import human36m_dataconf
from deephar.config import ntu_dataconf
from deephar.config import ntu_pe_dataconf
from deephar.config import ModelConfig
from deephar.config import DataConfig

from deephar.data import MpiiSinglePerson
from deephar.data import Human36M
from deephar.data import PennAction
from deephar.data import Ntu
from deephar.data import BatchLoader

from deephar.losses import pose_regression_loss
from keras.optimizers import RMSprop
from keras.optimizers import SGD
import keras.backend as K

from deephar.callbacks import SaveModel

from deephar.trainer import MultiModelTrainer
from deephar.models import compile_split_models
from deephar.models import spnet
from deephar.utils import *

sys.path.append(os.path.join(os.getcwd(), 'exp/common'))
#from datasetpath import datasetpath

from mpii_tools import MpiiEvalCallback
from h36m_tools import H36MEvalCallback
from ntu_tools import NtuEvalCallback

logdir = './'
if len(sys.argv) > 1:
    logdir = sys.argv[1]
    mkdir(logdir)
    sys.stdout = open(str(logdir) + '/log.txt', 'w')

num_frames = 6
cfg = ModelConfig((num_frames,) + ntu_dataconf.input_shape, pa17j3d,
        # num_actions=[60], num_pyramids=8, action_pyramids=[5, 6, 7, 8],
        num_actions=[60], num_pyramids=2, action_pyramids=[1, 2],
        num_levels=4, pose_replica=False,
        num_pose_features=192, num_visual_features=192)

num_predictions = spnet.get_num_predictions(cfg.num_pyramids, cfg.num_levels)
num_action_predictions = \
        spnet.get_num_predictions(len(cfg.action_pyramids), cfg.num_levels)

start_lr = 0.01
action_weight = 0.1
#batch_size_mpii = 3
#batch_size_h36m = 4
#batch_size_ntu = 6 #1
batch_clips = 3 # 8/4


"""Build the full model"""
full_model = spnet.build(cfg)

"""Load pre-trained weights from pose estimation and copy replica layers."""
full_model.load_weights(
         "E:\\Bachelorarbeit-SS20\\weights\\deephar\\output\\spnet\\0429\\weights_3dp+ntu_ar_048.hdf5",
         by_name=True)

"""Save model callback."""

save_model = SaveModel(os.path.join("C:\\networks\\deephar\\output\\spnet\\0505\\",
    'weights_3dp+benset_ar_{epoch:03d}.hdf5'), model_to_save=full_model)


def prepare_training(pose_trainable, lr):
    optimizer = SGD(lr=lr, momentum=0.9, nesterov=True)
    # optimizer = RMSprop(lr=lr)
    models = compile_split_models(full_model, cfg, optimizer,
            pose_trainable=pose_trainable, ar_loss_weights=action_weight,
            copy_replica=cfg.pose_replica)
    full_model.summary()

    """Create validation callbacks."""
    # mpii_callback = MpiiEvalCallback(mpii_x_val, mpii_p_val, mpii_afmat_val,
            # mpii_head_val, eval_model=models[0], pred_per_block=1,
            # map_to_pa16j=pa17j3d.map_to_pa16j, batch_size=1, logdir=logdir)

    # h36m_callback = H36MEvalCallback(h36m_x_val, h36m_pw_val, h36m_afmat_val,
            # h36m_puvd_val[:,0,2], h36m_scam_val, h36m_action,
            # batch_size=1, eval_model=models[0], logdir=logdir)

    ntu_callback = NtuEvalCallback(ntu_te, eval_model=models[1], logdir=logdir)

    def end_of_epoch_callback(epoch):

        save_model.on_epoch_end(epoch)
        # if epoch == 0 or epoch >= 50:
        # mpii_callback.on_epoch_end(epoch)
        # h36m_callback.on_epoch_end(epoch)

        ntu_callback.on_epoch_end(epoch)

        if epoch in [58, 70]:
            lr = float(K.get_value(optimizer.lr))
            newlr = 0.1*lr
            K.set_value(optimizer.lr, newlr)
            printcn(WARNING, 'lr_scheduler: lr %g -> %g @ %d' \
                    % (lr, newlr, epoch))

    return end_of_epoch_callback, models



steps_per_epoch = ntu.get_length(TRAIN_MODE) // batch_clips

fcallback, models = prepare_training(False, start_lr)
# trainer = MultiModelTrainer(models[1:], [ar_data_tr], workers=8,
        # print_full_losses=True)
# trainer.train(50, steps_per_epoch=steps_per_epoch, initial_epoch=0,
        # end_of_epoch_callback=fcallback)

"""Joint learning the full model."""
# steps_per_epoch = mpii.get_length(TRAIN_MODE) // (batch_size_mpii * batch_clips)

fcallback, models = prepare_training(True, 0.1*start_lr)
# trainer = MultiModelTrainer(models, [pe_data_tr, ar_data_tr], workers=8,
trainer = MultiModelTrainer(models, [pe_data_tr, ar_data_tr], workers=4,
        print_full_losses=True)
trainer.train(90, steps_per_epoch=steps_per_epoch, initial_epoch=20,
        end_of_epoch_callback=fcallback)
