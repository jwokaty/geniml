#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import numpy as np
from multiprocessing import Pool
from .utils import process_db_line, prep_data, check_if_uni_sorted
from ..utils import natural_chr_sort
import tempfile


def flexible_distance(r, q):
    """Calculate distance between region and flexible region from flexible universe
    :param [int, int] r: region from flexible universe
    :param int q: analysed region
    :return int: distance
    """
    if r[0] <= q <= r[1]:
        return 0
    else:
        return min(abs(r[0] - q), abs(r[1] - q))


def distance(r, q):
    """Calculate distance between region and region from hard universe
    :param [int] r: region from hard universe
    :param int q: analysed region
    :return int: distance
    """
    return abs(r[0] - q)


def asses(db, db_que, i, current_chrom, unused_db, pos_index, flexible, uni_to_file):
    """
    Calculate distance from given peak to the closest region in universe
    :param file db: universe file
    :param list db_que: que of last three positions in universe
    :param int i: analysed position from the query
    :param str current_chrom: current analysed chromosome from query
    :param list unused_db: list of positions from universe that were not compared to query
    :param list pos_index: which indexes from universe BED file line should be used in analysis
    :param bool flexible: whether the universe if flexible
    :return int: peak distance to universe
    """
    if flexible:
        if uni_to_file:
            dist_to_db_que = [flexible_distance(i, j[0]) for j in db_que]
        else:
            dist_to_db_que = [flexible_distance(j, i) for j in db_que]
    else:
        dist_to_db_que = [distance(j, i) for j in db_que]
    min_pos = np.argmin(dist_to_db_que)
    while min_pos == 2:
        d = db.readline().strip("\n")
        if d == "":
            return dist_to_db_que[min_pos]
        pos, pos_chrom = process_db_line(d, pos_index)
        if pos_chrom != current_chrom:
            unused_db.append([pos, pos_chrom])
            return dist_to_db_que[min_pos]
        db_que[:-1] = db_que[1:]
        db_que[-1] = pos
        if flexible:
            if uni_to_file:
                dist_to_db_que = [flexible_distance(i, j[0]) for j in db_que]
            else:
                dist_to_db_que = [flexible_distance(j, i) for j in db_que]
        else:
            dist_to_db_que = [distance(j, i) for j in db_que]
        min_pos = np.argmin(dist_to_db_que)
    return dist_to_db_que[min_pos]


def process_line(
    db,
    q_chrom,
    current_chrom,
    unused_db,
    db_que,
    dist,
    waiting,
    start,
    pos_index,
    flexible,
    uni_to_file,
):
    """
    Calculate distance from new peak to universe
    :param file db: universe file
    :param str q_chrom: new peak's chromosome
    :param str current_chrom: chromosome that was analysed so far
    :param list unused_db: list of positions from universe that were not compared to query
    :param list db_que: que of three last positions in universe
    :param list dist: list of all calculated distances
    :param bool waiting: whether iterating through file, without calculating
     distance,  if present chromosome not present in universe
    :param int start: analysed position from the query
    :param list pos_index: which indexes from universe region use to calculate distance
    :param bool flexible: whether the universe if flexible
    :return bool, str: if iterating through chromosome not present in universe; current chromosome in query
    """
    if q_chrom != current_chrom:
        # change chromosome
        db_que.clear()
        # clean up the que
        if len(unused_db) == 0:
            d = db.readline().strip("\n")
            if d == "":
                waiting = True
                return waiting, current_chrom
            d_start, d_start_chrom = process_db_line(d, pos_index)
            while current_chrom == d_start_chrom:
                # finish reading old chromosome in DB file
                d = db.readline().strip("\n")
                if d == "":
                    break
                d_start, d_start_chrom = process_db_line(d, pos_index)
            unused_db.append([d_start, d_start_chrom])
        current_chrom = q_chrom
        if current_chrom == unused_db[-1][1]:
            waiting = False
            db_que.append(unused_db[-1][0])
            unused_db.clear()
        elif natural_chr_sort(unused_db[-1][1], current_chrom) == 1:
            # chrom present in file not in DB
            waiting = True
            return waiting, current_chrom
        while len(db_que) < 3:
            d = db.readline().strip("\n")
            if d == "":
                break
            d_start, d_start_chrom = process_db_line(d, pos_index)
            if d_start_chrom == current_chrom:
                db_que.append(d_start)
            elif natural_chr_sort(d_start_chrom, current_chrom) == 1:
                unused_db.append([d_start, d_start_chrom])
                waiting = True
                return waiting, current_chrom
    if len(db_que) == 0:
        waiting = True
    if not waiting:
        res = asses(
            db,
            db_que,
            start,
            current_chrom,
            unused_db,
            pos_index,
            flexible,
            uni_to_file,
        )
        dist.append(res)
    return waiting, current_chrom


def calc_distance_main(
    q,
    db_start,
    db_end,
    q_file,
    flexible,
    save_each,
    folder_out,
    pref,
    uni_to_file=False,
):
    db_que_start = []
    current_chrom_start = "chr0"
    dist_start = []
    unused_db_start = []
    waiting_start = False
    db_que_end = []
    current_chrom_end = "chr0"
    dist_end = []
    unused_db_end = []
    waiting_end = False
    pos_start = [1]
    pos_end = [2]
    if flexible and not uni_to_file:
        pos_start = [1, 6]
        pos_end = [7, 2]
    for i in q:
        if not uni_to_file:
            i = i.decode("utf-8")
        i = i.split("\t")
        if uni_to_file and flexible:
            start = [int(i[1]), int(i[6])]
            end = [int(i[7]), int(i[2])]
        else:
            start = int(i[1])
            end = int(i[2])
        q_chrom = i[0]
        res_start = process_line(
            db_start,
            q_chrom,
            current_chrom_start,
            unused_db_start,
            db_que_start,
            dist_start,
            waiting_start,
            start,
            pos_start,
            flexible,
            uni_to_file,
        )
        (waiting_start, current_chrom_start) = res_start
        res_end = process_line(
            db_end,
            q_chrom,
            current_chrom_end,
            unused_db_end,
            db_que_end,
            dist_end,
            waiting_end,
            end,
            pos_end,
            flexible,
            uni_to_file,
        )
        (waiting_end, current_chrom_end) = res_end
    q.close()
    if save_each:
        with open(os.path.join(folder_out, pref, q_file), "w") as f:
            for i, j in zip(dist_start, dist_end):
                f.write(f"{i}\t{j}\n")
    if not dist_start:
        print(f"File {q_file} doesn't contain any chromosomes present in universe")
        return q_file, None
    dist = dist_start + dist_end
    return q_file, np.median(dist)


def calc_distance_file(
    db_file,
    q_folder,
    q_file,
    flexible=False,
    save_each=False,
    folder_out=None,
    pref=None,
):
    """
    For given file calculate distances to the nearst region from universe
    :param str db_file: path to universe
    :param str q_folder: path to folder containing query files
    :param str q_file: query file
    :param boolean flexible: whether the universe if flexible
    :param bool save_each: whether to save calculated distances for each file
    :param str folder_out: output name
    :param str pref: prefix used as the name of the name
     containing calculated distance for each file
    :return str, int, int: file name; median od distance of starts to
     starts in universe; median od distance of ends to ends in universe
    """
    q = tempfile.NamedTemporaryFile()
    prep_data(q_folder, q_file, q)
    db_start = open(db_file)
    db_end = open(db_file)
    return calc_distance_main(
        q,
        db_start,
        db_end,
        q_file,
        flexible,
        save_each,
        folder_out,
        pref,
    )


def calc_distance_uni(
    universe,
    q_folder,
    q_file,
    flexible=False,
    save_each=False,
    folder_out=None,
    pref=None,
):
    """
    For given universe calculate distances to the nearst region from combined collection
    :param str db_file_start: path to combined peaks sorted by starts, with removed duplicated start
    :param str db_file_end: path to combined peaks sorted by ends, with removed duplicated start
    :param str q_folder: path to folder with universe
    :param str q_file: universe
    :param boolean flexible: whether the universe if flexible
    :param bool save_each: whether to save calculated distances for each file
    :param str folder_out: output name
    :param str pref: prefix used as the name of the name
     containing calculated distance for each file
    :return str, int, int: file name; median od distance of starts to
     starts in universe; median od distance of ends to ends in universe
    """
    q = tempfile.NamedTemporaryFile()
    prep_data(q_folder, q_file, q)
    db_start = open(q.name)
    db_end = open(q.name)
    uni = open(universe)
    return calc_distance_main(
        uni,
        db_start,
        db_end,
        q_file,
        flexible,
        save_each,
        folder_out,
        pref,
        uni_to_file=True,
    )


def run_distance(
    folder,
    file_list,
    universe,
    no_workers,
    flexible=False,
    save_to_file=False,
    folder_out=None,
    pref=None,
    save_each=False,
    uni_to_file=False,
):
    """
    For group of files calculate distances to the nearest region in universe
    :param str folder: path to name containing query files
    :param str file_list: path to file containing list of query files
    :param str universe: path to universe file
    :param int no_workers: number of parallel processes
    :param bool flexible: whether the universe if flexible
    :param bool save_to_file: whether to save median of calculated distances for each file
    :param str folder_out: output name
    :param str pref: prefix used for saving
    :param bool save_each: whether to save calculated distances for each file
    :return float; float: mean of median distances from starts in query to the nearest starts in universe;
    mean of median distances from ends in query to the nearest ends in universe
    """
    check_if_uni_sorted(universe)
    files = open(file_list).read().split("\n")[:-1]
    res = []
    if folder_out:
        os.makedirs(folder_out, exist_ok=True)
    if save_each:
        os.makedirs(os.path.join(folder_out, pref), exist_ok=True)
    if uni_to_file:
        dist_function = calc_distance_uni
    else:
        dist_function = calc_distance_file
    if no_workers <= 1:
        for i in files:
            r = dist_function(
                universe, folder, i, flexible, save_each, folder_out, pref
            )
            res.append(r)
    else:
        with Pool(no_workers) as p:
            args = [
                (universe, folder, f, flexible, save_each, folder_out, pref)
                for f in files
            ]
            res = p.starmap(dist_function, args)
    if save_to_file:
        file_out = os.path.join(folder_out, pref + "_data.tsv")
        with open(file_out, "w") as o:
            o.write("file\tmedian_dist\n")
            for r in res:
                o.write(f"{r[0]}\t{r[1]}\n")
    else:
        res = np.array(res)
        res = res[:, 1]
        res = res.astype("float")
        return np.mean(res)
