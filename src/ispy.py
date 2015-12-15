#!/usr/bin/env python
__author__ = 'jesse'

import rospy
import random
import pickle
import IspyAgent
from agent_io import *
from perception_classifiers.srv import *


# rosrun nlu_pipeline ispy.py [object_IDs] [num_rounds] [stopwords_fn] [user_id] [simulation=True/False] [agent_to_load]
# start a game of ispy with user_id or with the keyboard/screen
# if user_id provided, agents are pickled so that an aggregator can later extract
# all examples across users for retraining classifiers and performing splits/merges
# is user_id not provided, classifiers are retrained and saved after each game with just single-user data
def main():

    path_to_ispy = '/u/jesse/public_html/ispy'
    path_to_logs = '/u/jesse/catkin_ws/src/perception_classifiers/logs/'
    pp = os.path.join(path_to_ispy, "pickles")
    if not os.path.isdir(pp):
        os.system("mkdir "+pp)
        os.system("chmod 777 "+pp)
    cp = os.path.join(path_to_ispy, "communications")
    if not os.path.isdir(cp):
        os.system("mkdir "+cp)
        os.system("chmod 777 "+cp)

    object_IDs = [int(oid) for oid in sys.argv[1].split(',')]
    num_rounds = int(sys.argv[2])
    stopwords_fn = sys.argv[3]
    user_id = sys.argv[4]
    simulation = True if sys.argv[5] == "True" else False
    agent_fn = sys.argv[6] if len(sys.argv) == 7 else None

    log_fn = os.path.join(path_to_logs, user_id+".trans.log")
    f = open(log_fn, 'a')
    f.write("object_IDs:"+str(object_IDs)+"\n")
    f.write("num_rounds:"+str(num_rounds)+"\n")
    f.write("agent_fn:"+str(agent_fn)+"\n")
    f.close()

    print "calling ROSpy init"
    node_name = 'ispy' if user_id is None else 'ispy' + str(user_id)
    rospy.init_node(node_name)

    print "instantiating ispyAgent"
    if agent_fn is not None and os.path.isfile(os.path.join(pp, agent_fn)):
        print "... from file"
        f = open(os.path.join(pp, agent_fn), 'rb')
        A = pickle.load(f)
        A.object_IDs = object_IDs
        A.log_fn = log_fn
        f.close()
        print "... loading perceptual classifiers"
        A.load_classifiers()
    else:
        A = IspyAgent.IspyAgent(None, None, object_IDs, stopwords_fn, log_fn=log_fn)
    if user_id is None:
        u_in = InputFromKeyboard()
        u_out = OutputToStdout()
    else:
        u_in = InputFromFile(os.path.join(cp, user_id+".get.in"),
                             os.path.join(cp, user_id+".guess.in"),
                             log_fn)
        u_out = OutputToFile(os.path.join(cp, user_id+".say.out"),
                             os.path.join(cp, user_id+".point.out"),
                             log_fn)
    A.u_in = u_in
    A.u_out = u_out
    A.simulation = simulation

    print "beginning game"
    for rnd in range(0, num_rounds):

        # human turn
        h_utterance, h_cnfs, correct_idx = A.human_take_turn()
        if correct_idx is not None:
            for d in h_cnfs:
                for pred in d:
                    A.update_predicate_data(pred, [[object_IDs[correct_idx], True]])

        # robot turn
        idx_selection = correct_idx
        while idx_selection == correct_idx:
            idx_selection = random.randint(0, len(object_IDs)-1)
        r_utterance, r_predicates, num_guesses = A.robot_take_turn(idx_selection)
        labels = A.elicit_labels_for_predicates_of_object(idx_selection, r_predicates)
        for idx in range(0, len(r_predicates)):
            A.update_predicate_data(r_predicates[idx], [[object_IDs[idx_selection], labels[idx]]])
    A.u_out.say("Thanks for playing!")

    f = open(os.path.join(pp, "-".join([str(oid) for oid in object_IDs])+"_"+user_id+".agent"), 'wb')
    pickle.dump(A, f)
    f.close()


if __name__ == "__main__":
        main()
