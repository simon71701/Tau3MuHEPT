import shutil
import torch
import torch.nn as nn
from torch.nn.utils import clip_grad_norm_
import yaml
from datetime import datetime
from tqdm import tqdm
from pathlib import Path
import numpy as np
from sklearn.metrics import roc_auc_score, roc_curve
import matplotlib.pyplot as plt

from utils import ClusterLoss, Writer, log_epoch, load_checkpoint, save_checkpoint, set_seed, add_cuts_to_config
from utils import get_data_loaders_contrastive as get_data_loaders

from models.get_model import get_model


@torch.no_grad()
def eval_one_batch(model, criterion, pos_batch, device='cuda:0'):
    model.to(device)
    model.eval()

    with torch.no_grad():
        pos_batch.to(device)
        
        pos_embeds = model(pos_batch.x, pos_batch.coords, pos_batch.batch, pool=False)
        
        with torch.no_grad():
            scores, _ = criterion.cluster(pos_embeds.cpu())

        return scores
        
def run_one_epoch(model, criterion, pos_loader):
    
    loader_len = len(pos_loader)

    all_scores = []
    all_targets = []
    
    pbar = tqdm(pos_loader, total=loader_len)

    for idx, pos_batch in enumerate(pbar):
        
        scores = eval_one_batch(model, criterion, pos_batch)
        
        scores.to('cpu')
        
        all_scores.append(scores)
        all_targets.append(pos_batch.hit_truth.cpu())
    
    
    all_scores = torch.cat(all_scores,dim=1).numpy()
    all_targets = torch.cat(all_targets)
    
    labels = [0,1,2,3]
    
    fprs = []
    tprs = []
    threshes = []
    aucs = []
    for label in labels:
        targets = torch.where(all_targets==label, 1, 0).numpy()
        
        fpr, tpr, thresholds = roc_curve(targets, all_scores[label])
        auc = roc_auc_score(targets, all_scores[label])
        print(label, auc)
        
        fprs.append(fpr)
        tprs.append(tpr)
        threshes.append(thresholds)
        aucs.append(auc)
        
    return fprs, tprs, threshes, aucs
    
    
def main():
    
    import argparse
    parser = argparse.ArgumentParser(description='Train Tau3MuGNNs')
    parser.add_argument('--setting', type=str, help='experiment settings', default='GNN_half_dR_1')
    parser.add_argument('--cuda', type=int, help='cuda device id, -1 for cpu', default=3)
    parser.add_argument('--log', type=str, help='experiment settings', default='GNN_half_dR_1')
    
    args = parser.parse_args()
    setting = args.setting
    cuda_id = args.cuda
    log = args.log
    
    log_dir = f'/depot/cms/users/simon73/Tau3MuHEPT/data/{log}'
    
    torch.set_num_threads(5)
    set_seed(42)
    
    config = yaml.safe_load(Path(f'{log_dir}/config.yml').open('r'))
    device = torch.device(f'cuda:{cuda_id}' if cuda_id >= 0 else 'cpu')
    
    data_loaders, x_dim, dataset = get_data_loaders(setting, config['data'], config['optimizer']['batch_size'], endcap=0)

    model = get_model(config['model_kwargs'],dataset)  
    
    checkpoint = torch.load(f'{log_dir}/model.pt')
    
    model_state_dict = checkpoint['model_state_dict']
    
    model.load_state_dict(model_state_dict)
    
    criterion = checkpoint['criterion']
    pos_loader = data_loaders['test'][0]
    
    fpr, tpr, thresholds, auc = run_one_epoch(model, criterion, pos_loader)
    
    torch.save({
        'fpr': fpr,
        'tpr': tpr,
        'thresholds': thresholds,
        'auc': auc
        }, f'{log_dir}/roc.pt')
    
if __name__ == '__main__':
    import os
    os.chdir('./src')
    main()
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    