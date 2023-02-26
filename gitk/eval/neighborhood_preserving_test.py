import pickle
import os
os.environ["OPENBLAS_NUM_THREADS"] = "1"
import numpy as np
import time
import argparse
from gensim.models import Word2Vec
import time
import multiprocessing as mp
from gitk.eval import load_genomic_embeddings
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

class Timer():
    def __init__(self):
        self.o = time.time()

    def measure(self, p=1):
        x = (time.time() - self.o) / float(p)
        x = int(x)
        if x >= 3600:
            return '{:.1f}h'.format(x / 3600)
        if x >= 60:
            return '{}m'.format(round(x / 60))
        return '{}s'.format(x)
# function calculating the chromosome distance between two regions
func_rdist = lambda u,v:float(u[1]<v[1])*max(v[0]-u[1]+1,0)+float(u[1]>=v[1])*max(u[0]-v[1]+1,0)

def get_topk_embed(i, K, embed, dist='euclidean'):
    """
    Return the indices for the most similar K regions to the i-th region
    embed is the embedding matrix for all the regions in the vocabulary of a region2vec model
    """
    num = len(embed)
    if dist == 'cosine':
        nom = np.dot(embed[i:i+1], embed.T)
        denom = np.linalg.norm(embed[i:i+1]) * np.linalg.norm(embed,axis=1)
        sims = (nom / denom)[0]
        indexes = np.argsort(-sims)[1:K+1]
        s = sims[indexes]
    elif dist == 'euclidean':
        dist = np.linalg.norm(embed[i:i+1] - embed, axis=1)
        indexes = np.argsort(dist)[1:K+1]
        s = -dist[indexes]
    elif dist == 'jaccard':
        nom = np.dot(embed[i:i+1], embed.T)
        denom = ((embed[i:i+1] + embed)>0.0).sum(axis=1)
        sims = (nom / denom)[0]
        indexes = np.argsort(-sims)[1:K+1]
        s = sims[indexes]
    return indexes, s

def find_Kneighbors(region_array, index, K):
    """
    region_array must be sorted; all regions are on the same chromosome
    index is the index for the query region region_array[index]
    K is the number of nearest neighbors of the query region
    
    return: indices of the K nearest neighbors in region_array
    """
    if len(region_array) < K:
        K = len(region_array)
    qregion = region_array[index]
    left_idx = max(index - K, 0)
    right_idx = min(index + K, len(region_array)-1)
    rdist_arr = []
    for idx in range(left_idx,right_idx+1):
        rdist_arr.append(func_rdist(qregion, region_array[idx]))
    rdist_arr = np.array(rdist_arr)
    Kneighbors_idx = np.argsort(rdist_arr)[1:K+1]
    Kneighbors_idx = Kneighbors_idx + left_idx
    return Kneighbors_idx

def calculate_overlap(i, K, chromo, region_array, region2index, embed_rep):
    Kindices = find_Kneighbors(region_array, i, K)
    if len(Kindices) == 0:
        return 0
    str_kregions = ['{}:{}-{}'.format(chromo, *region_array[k]) for k in Kindices] # sorted in ascending order
    _Krdist_global_indices = np.array([region2index[r] for r in str_kregions])
    
    idx = region2index['{}:{}-{}'.format(chromo, *region_array[i])]
    _Kedist_global_indices, _ = get_topk_embed(idx, K, embed_rep) # sorted in ascending order
   
    overlap = len(set(_Krdist_global_indices).intersection(set(_Kedist_global_indices)))
    return overlap

def calculate_overlap_bins(i, K, chromo, region_array, region2index, embed_rep, res=50):
    Kindices = find_Kneighbors(region_array, i, K)
    if len(Kindices) == 0:
        return 0
    str_kregions = ['{}:{}-{}'.format(chromo, *region_array[k]) for k in Kindices] # sorted in ascending order
    _Krdist_global_indices = np.array([region2index[r] for r in str_kregions])
    
    idx = region2index['{}:{}-{}'.format(chromo, *region_array[i])]
    _Kedist_global_indices, _ = get_topk_embed(idx, K, embed_rep) # sorted in ascending order
    
    bin_overlaps = []
    prev = 0
    assert res < K + 1, "resolution < K + 1"
    for i in range(res,K+1,res):
        set1 = set(_Krdist_global_indices[prev:i])
        set2 = set(_Kedist_global_indices[prev:i])
        
        overlap = len(set1.intersection(set2))/min(i, len(set1))
        bin_overlaps.append(overlap)
    
    return np.array(bin_overlaps)



def calculate_overlap_same_chromosome(i, K, chromo, region_array, embed_rep, dist):
    _Krindices = find_Kneighbors(region_array, i, K)
    if len(_Krindices) == 0:
        return np.zeros(K)
    Krindices = np.ones(K) * (-1)
    Krindices[0:len(_Krindices)] = _Krindices

    _Keindices, _ = get_topk_embed(i, K, embed_rep, dist)
    Keindices = np.ones(K) * (-2)
    Keindices[0:len(_Keindices)] = _Keindices

    # overlap = set(Krindices).intersection(set(Keindices))
    overlap = (Krindices == Keindices).astype(np.float)
    return overlap

def cal_snpr(ratio_embed, ratio_random):
    return np.log10((ratio_embed+1.e-10)/(ratio_random+1.e-10))



var_dict = {}
def worker_func(i, K, chromo, region_array, embed_type, resolution):
    if embed_type == 'embed':
        embeds = var_dict['embed_rep']
    elif embed_type == 'random':
        embeds = var_dict['ref_embed']
    nprs = calculate_overlap_bins(i, K, chromo, region_array, var_dict['region2vec_index'], embeds, resolution)
    return nprs

def init_worker(embed_rep, ref_embed, region2index):
        var_dict['embed_rep'] = embed_rep
        var_dict['ref_embed'] = ref_embed
        var_dict['region2vec_index'] = region2index

def neighborhood_preserving_test(model_path, embed_type, K, num_samples=100, seed=0, resolution=None, num_workers=10):
    """
    If sampling > 0, then randomly sample num_samples regions in total (proportional for each chromosome)
    
    If num_samples == 0, all regions are used in calculation
    """
    embed_rep, regions_r2v = load_genomic_embeddings(model_path, embed_type)
    timer = Timer()
    if resolution is None:
        resolution = K

    region2index = {r:i for i,r in enumerate(regions_r2v)}
    # Group regions by chromosomes
    chromo_regions = {}
    for v in regions_r2v:
        chromo, region = v.split(':') # e.g. chr1:100-1000
        chromo = chromo.strip() # remove possible spaces
        region = region.strip() # remove possible spaces
        start, end = region.split('-')
        start = int(start.strip())
        end = int(end.strip())
        if chromo not in chromo_regions:
            chromo_regions[chromo] = [(start,end)]
        else:
            chromo_regions[chromo].append((start,end))
            
    # sort regions in each chromosome
    chromo_ratios = {}
    for chromo in chromo_regions:
        region_array = chromo_regions[chromo]
        chromo_regions[chromo] = sorted(region_array, key=lambda x: x[0])
        chromo_ratios[chromo] = len(region_array)/len(regions_r2v)

    num_regions, num_dim = embed_rep.shape

    np.random.seed(seed)
    
    ref_embed = (np.random.rand(num_regions, num_dim) - 0.5)/num_dim

    avg_ratio = 0.0
    avg_ratio_ref = 0.0
    count = 0

    with mp.Pool(processes=num_workers,initializer=init_worker, initargs=(embed_rep,ref_embed, region2index)) as pool:
        all_processes = []
        for chromo in chromo_regions:
            region_array = chromo_regions[chromo]
            if num_samples == 0: # exhaustive
                indexes = list(range(len(region_array)))
            else:
                num = min(len(region_array),round(num_samples*chromo_ratios[chromo]))
                indexes = np.random.permutation(len(region_array))[0:num]
            for i in indexes:
                process_embed = pool.apply_async(worker_func, (i, K, chromo, region_array, 'embed', resolution))
                process_random = pool.apply_async(worker_func, (i, K, chromo, region_array, 'random', resolution))
                all_processes.append((process_embed,process_random))
        
        for i,(process_embed,process_random)  in enumerate(all_processes):
            avg_ratio = (avg_ratio * count + process_embed.get())/(count+1)
            avg_ratio_ref = (avg_ratio_ref * count + process_random.get())/(count+1)
            count = count + 1
    snprs = cal_snpr(avg_ratio, avg_ratio_ref)

    ratio_msg = ' '.join(['{:.6f}'.format(r) for r in avg_ratio])
    ratio_ref_msg = ' '.join(['{:.6f}'.format(r) for r in avg_ratio_ref])
    snprs_msg = ' '.join(['{:.6f}'.format(r) for r in snprs])
    print(model_path)
    
    print('[seed={}] K={}\n[{}]: {}\n[Random]: {}\n[SNPR] {}'.format(seed, K, embed_type, ratio_msg, ratio_ref_msg, snprs_msg))
    result = {'K':K, 'AvgENPR':avg_ratio, 'AvgRNPR':avg_ratio_ref, 'SNPR': snprs, 'Path': model_path}
    elapsed_time = timer.measure()
    print('Elapsed time:', elapsed_time)
    return result


def writer_multiprocessing(save_path, num, q):
    results = [[]for i in range(num)]
    while True:
        m = q.get()
        if m == 'kill':
            break
        worker_id = m[0]
        results[worker_id] = m[1]
        if save_path:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, 'wb') as f:
                pickle.dump(results, f)
    return results
        
def neighborhood_preserving_test_batch(batch, K, num_samples=100, num_workers=10, seed=0, save_path=None):
    print('Total number of models: {}'.format(len(batch)))
    result_list = []
    for index, (path, embed_type) in enumerate(batch):
        result = neighborhood_preserving_test(path, embed_type, K, num_samples, seed, K, num_workers)
        result_list.append(result)
    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, 'wb') as f:
            pickle.dump(result_list, f)
    return result_list

def npt_eval(batch, K, num_samples=100, num_workers=10, num_runs=20, save_folder=None):
    results_seeds = []
    for seed in range(num_runs):
        print('----------------Run {}----------------'.format(seed))
        save_path = os.path.join(save_folder,'npt_eval_seed{}'.format(seed)) if save_folder else None
        result_list = neighborhood_preserving_test_batch(batch, K, num_samples=num_samples, num_workers=num_workers, seed=seed, save_path=save_path)
        results_seeds.append(result_list)
    snpr_results = [[] for i in range(len(batch))]
    paths = ['' for i in range(len(batch))]
    for results in results_seeds:
        for i, result in enumerate(results):
            key = result['Path']
            snpr_results[i].append(result['SNPR'])
            paths[i] = key
    snpr_results = [np.array(v) for v in snpr_results]
    print(snpr_results[0].shape)
    for i in range(len(batch)):
        print('{}\nSNPR_Avg (std):{:.6f} ({:.6f})'.format(paths[i], snpr_results[i][:,0].mean(),snpr_results[i][:,0].std()))
    snpr_results = [(paths[i],snpr_results[i]) for i in range(len(batch))]
    return snpr_results
    

def get_npt_results(save_paths):
    snpr_results = {}
    for save_path in save_paths:
        with open(save_path,'rb') as f:
            results = pickle.load(f)
            for result in results:
                key = result['Path']
                if key in snpr_results:
                    snpr_results[key].append(result['SNPR'])
                else:
                    snpr_results[key] = [result['SNPR']]
    snpr_results = [(k,np.array(v)) for k,v in snpr_results.items()]
    return snpr_results

def snpr_plot(snpr_data, row_labels=None, legend_pos=(0.25, 0.6), filename=None):
    snpr_vals = [(k,v[:,0].mean(),v[:,0].std()) for k,v in snpr_data]
    cmap = plt.get_cmap('Set1')
    cmaplist = [cmap(i) for i in range(9)]
    if row_labels is None:
        row_labels = [k for k, v, s in snpr_vals]
    fig, ax = plt.subplots(figsize=(10,6))
    mean_snpr_tuple = [(i,r[1]) for i,r in enumerate(snpr_vals)]
    mean_snpr_tuple = sorted(mean_snpr_tuple, key=lambda x:-x[1])
    mean_snpr = [t[1] for t in mean_snpr_tuple]
    indexes = [t[0] for t in mean_snpr_tuple]
    std_snpr = [snpr_vals[i][2] for i in indexes]
    row_labels = [row_labels[i] for i in indexes]
    ax.set_xticks(list(range(1,len(mean_snpr)+1)))
    ax.set_xticklabels(row_labels)
    ax.errorbar(range(1,len(mean_snpr)+1), mean_snpr, yerr=std_snpr,fmt='o',ms=10, mfc=cmaplist[1], mec=cmaplist[8], ecolor=cmaplist[2], elinewidth=3, capsize=5)
    ax.set_ylabel('SNPR')
    _ = plt.setp(ax.get_xticklabels(), rotation=-15, ha="left", va='top',
                rotation_mode="anchor")
    patches = [Line2D([0], [0], marker='o', linestyle='',color=cmaplist[1], markersize=12, mec=cmaplist[8]),
               Line2D([0], [0], color=cmaplist[2], lw=4)]
    legend = ax.legend(labels=['SNPR','SNPR standard deviation'], handles=patches, bbox_to_anchor=legend_pos, loc='center left', borderaxespad=0, fontsize=12, frameon=True)
    ax.grid('on')
    if filename:
        fig.savefig(filename,bbox_inches='tight')
