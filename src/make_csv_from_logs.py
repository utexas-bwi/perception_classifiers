#!/usr/bin/env python
__author__ = 'jesse'

import ast
import numpy as np
import operator
import os
from argparse import ArgumentParser


def main(args):

    # Directory structure:
    # exp/
    #   objects/  # these are shared across all conditions
    #       oidxs.pickle, features.pickle
    #   fold0/, fold1/, ...  # each subsequent fold generated from previous; fold0 created by hand
    #       cond1/, cond2/
    #           source/  # contains pre-trained classifiers and preds from all PREVIOUS folds
    #               labels.pickle, predicates.pickle, classifiers.pickle
    #           uid0/, uid1/, ...
    #               toidx0_toidx1_toidx2_toidx3, ...  # directories named for test object ids (4 each, 2 dirs)
    #                   log.txt
    #                   source/  # contains re-trained classifiers and new preds from dialog after the game
    #                       labels.pickle, objects.pickle, predicates.pickle, classifiers.pickle

    user_data = []  # each row represents a test_oidx combo for a user
    max_preds = None  # (num, id)
    min_preds = None  # (num, id)
    obj_descs = {}  # indexed by oidx, values lists of utterances describing corresponding object
    for fold_idx in range(4):
        fold_dir = os.path.join(args.exp_dir, 'fold' + str(fold_idx))
        if os.path.isdir(fold_dir):
            for cond in range(1, 3):  # conds 1, 2
                cond_dir = os.path.join(fold_dir, str(cond))
                for root, dirs, fns in os.walk(cond_dir):
                    if root == cond_dir:
                        for user_dir in [_d for _d in dirs if _d != "source"]:
                            uid = int(user_dir)
                            user_dir_to_walk = os.path.join(root, user_dir)
                            for uroot, udirs, ufns in os.walk(user_dir_to_walk):
                                if uroot == user_dir_to_walk:
                                    for toidx_dir in udirs:
                                        logfn = os.path.join(uroot, toidx_dir, "log.txt")
                                        toidxs = [int(toidx) for toidx in toidx_dir.split('_')]
                                        nb_q_init = 0
                                        nb_q_yn = 0
                                        nb_q_ex = 0
                                        nb_g = 0
                                        preds = None
                                        match_scores = None
                                        last_point = None
                                        last_touch = None
                                        correct_guess = True
                                        utterance = None
                                        last_get = None
                                        with open(logfn, 'r') as f:
                                            for line in f.readlines():
                                                line = line.strip()
                                                if len(line) == 0:
                                                    continue
                                                lp = line.split()
                                                if lp[0] == "Action":
                                                    if lp[2] == "get_initial_description":
                                                        nb_q_init += 1
                                                    elif lp[2] == "ask_predicate_label":
                                                        nb_q_yn += 1
                                                    elif lp[2] == "ask_positive_example":
                                                        nb_q_ex += 1
                                                    elif lp[2] == "make_guess":
                                                        nb_g += 1
                                                elif lp[0] == "Get":
                                                    last_get = ' '.join(lp[2:])
                                                elif lp[0] == "Predicates":
                                                    preds_a = [pred.strip("[]',") for pred in lp[2:]]
                                                    preds = '_'.join(preds_a)
                                                    if max_preds is None or len(preds_a) > max_preds[0]:
                                                        max_preds = [len(preds_a), uid]
                                                    elif len(preds_a) == max_preds[0]:
                                                        max_preds.append(uid)
                                                    if min_preds is None or len(preds_a) < min_preds[0]:
                                                        min_preds = [len(preds_a), uid]
                                                    elif len(preds_a) == min_preds[0]:
                                                        min_preds.append(uid)
                                                    utterance = last_get
                                                elif lp[0] == "Match" and lp[2] == ":":
                                                    ms_str = ' '.join(lp[3:])
                                                    match_scores = ast.literal_eval(ms_str)
                                                elif "point:" in lp[0] and "-1" not in lp[0]:
                                                    last_point = int(lp[0][len("point:"):])
                                                elif "touch:" in lp[0]:
                                                    last_touch = int(lp[0][len("touch:"):])
                                                elif "Can you touch the object that you were describing?" in line:
                                                    correct_guess = False

                                        if correct_guess:
                                            right_ans = toidxs[last_point]
                                        else:
                                            right_ans = toidxs[last_touch]

                                        if right_ans not in obj_descs:
                                            obj_descs[right_ans] = [[utterance, toidxs]]
                                        else:
                                            obj_descs[right_ans].append([utterance, toidxs])

                                        # Correctness calculation: whether right object guessed (or tied)
                                        max_match_score = max([match_scores[toidx] for toidx in toidxs])
                                        ties = [toidx for toidx in toidxs
                                                if np.isclose(max_match_score, match_scores[toidx])]
                                        if right_ans in ties:
                                            correct = 1. / len(ties)
                                        else:
                                            correct = 0

                                        # Correctness calculation: rank of object in 0-3
                                        # sorted_scores = sorted(match_scores.items(), key=operator.itemgetter(1),
                                        #                        reverse=True)
                                        # rank = [idx for idx in range(len(sorted_scores))
                                        #         if sorted_scores[idx][0] == right_ans][0]
                                        # tied_ranks = [idx for idx in range(len(sorted_scores))
                                        #               if np.isclose(sorted_scores[rank][1], sorted_scores[idx][1])]
                                        # correct = np.mean(tied_ranks)

                                        # Correctness calculation: probability mass on correct object.
                                        # sum_scores = sum([match_scores[toidx] for toidx in toidxs])
                                        # correct = match_scores[right_ans] / sum_scores

                                        user_data.append([fold_idx, cond, uid, toidx_dir,
                                                          nb_q_init, nb_q_yn, nb_q_ex, nb_g, correct,
                                                          preds])
    print "min preds: " + str(min_preds)
    print "max preds: " + str(max_preds)

    # Write user data to file.
    with open(args.outfile, 'w') as f:
        f.write(','.join(["fold", "condition", "uid", "test_oidxs",
                          "nb_q_init", "nb_q_yn", "nb_q_ex", "nb_g", "correct",
                          "predicates_used"]) + '\n')
        for entry in user_data:
            f.write(','.join([str(d) for d in entry]) + '\n')

    with open(args.obj_desc_outfile, 'w') as f:
        for oidx in obj_descs:
            for u, toidxs in obj_descs[oidx]:
                f.write(str(oidx + 1) + ',' + ','.join([str(toidx + 1) for toidx in toidxs]) + ',' + u + '\n')


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--exp_dir', type=str, required=True,
                        help=("Directory where experiment data for this fold is held. " +
                              "Expects a source/ sub-directory with initial predicates, labels, " +
                              "and, for fold > 0, classifiers pickles."))
    parser.add_argument('--outfile', type=str, required=True,
                        help="CSV outfile summarizing information extracted from logs")
    parser.add_argument('--obj_desc_outfile', type=str, required=True,
                        help="CSV outfile of descriptions associated with objects")
    cmd_args = parser.parse_args()
    
    main(cmd_args)