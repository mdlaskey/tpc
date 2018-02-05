import tpc.config.config_tpc as cfg
import numpy as np
import IPython
import cv2
import os
import cPickle as pickle
from perception import ColorImage, BinaryImage
from tpc.perception.cluster_registration import display_grasps
from tpc.perception.singulation import display_singulation
from tpc.data_manager import DataManager

#to fix
#singulation success metric

if __name__ == "__main__":
    connected_components_times = []
    compute_grasps_times = []
    find_grasps_times = []
    execute_grasp_times = []
    execute_singulation_times = []
    compute_singulation_times = []

    grasp_successes = 0
    grasp_attempts = 0

    singulation_successes = 0
    singulation_attempts = 0

    color_successes = 0
    color_attempts = 0

    #for key k, corresponds to a list
    #each time k singulations are followed by succeeding in m out of n grasps, add (m, n) to list
    #this ignores some data from crashes between singulates and grasps
    #groups grasps in different but sequential trajectoreis
    num_singulates_to_num_grasps = {}


    grasp_crashes = 0
    singulate_crashes = 0
    completions = 0
    false_completions = 0
    total_stopped = 0

    grasps_per_rollout = []
    singulates_per_rollout = []

    actions_before_crash = []

    to_save_imgs_num = 20

    dm = DataManager(False)
    for rnum in range(dm.num_rollouts):
        rollout = dm.read_rollout(rnum)
        trajnum = 0
        rollout_grasps = 0
        rollout_singulates = 0
        actions = [t["action"] for t in rollout]

        curr_singulate_sequence = 0
        curr_grasp_sequence_s = 0
        curr_grasp_sequence_t = 0
        last_was_grasp = True
        for traj_ind, traj in enumerate(rollout):
            c_img = traj["c_img"]
            d_img = traj["d_img"]
            # c_after = traj["c_img_result"]
            # d_after = traj["d_img_result"]
            crop = traj["crop"]
            times = []
            connected_components_times.append(traj["connected_components_time"])
            compute_grasps_times.append(traj["compute_grasps_time"])
            find_grasps_times.append(traj["find_grasps_time"])
            action = traj["action"]
            info = traj["info"]
            succ = traj["success"]

            #some rollouts were made before this statistic was added
            if "stop_condition" in traj:
                if traj["stop_condition"] != "none":
                    actions_before_crash.append(traj_ind)
                    total_stopped += 1
                    stop = traj["stop_condition"]
                    if stop == "y":
                        completions += 1
                    elif stop == "n":
                        false_completions += 1
                    elif stop == "crash":
                        if action == "grasp":
                            grasp_crashes += 1
                        elif action =="singulate":
                            singulate_crashes += 1

            #check key in case crash during computation of grasps
            if action == "grasp":
                last_was_grasp = True
                if "execute_time" in traj:
                    execute_grasp_times += traj["execute_time"]
                cms = []
                dis = []
                for grasp in info:
                    cm, di, mask, class_num = grasp
                    cms.append(cm)
                    dis.append(di)
                if rnum == to_save_imgs_num:
                    display_grasps(ColorImage(c_img), cms, dis, name="debug_imgs/rollout_imgs/r" + str(trajnum))
                curr_grasp_successes = 0
                curr_grasp_attempts = 0
                for i, s in enumerate(succ):
                    if s != "?":
                        c = traj["color"][i]
                        curr_grasp_attempts += 1
                        if s == "y":
                            curr_grasp_successes += 1
                        if c == "y":
                            color_successes += 1
                grasp_attempts += curr_grasp_attempts
                color_attempts += curr_grasp_attempts
                rollout_grasps += curr_grasp_attempts
                grasp_successes += curr_grasp_successes
                curr_grasp_sequence_t += curr_grasp_attempts
                curr_grasp_sequence_s += curr_grasp_successes

            elif action == "singulate":
                if last_was_grasp and curr_grasp_sequence_t > 0:
                    if curr_singulate_sequence not in num_singulates_to_num_grasps:
                        num_singulates_to_num_grasps[curr_singulate_sequence] = []
                    num_singulates_to_num_grasps[curr_singulate_sequence].append((curr_grasp_sequence_s, curr_grasp_sequence_t))
                    curr_grasp_sequence_s = 0
                    curr_grasp_sequence_t = 0
                    curr_singulate_sequence = 0
                last_was_grasp = False
                curr_singulate_sequence += 1
                rollout_singulates += 1
                compute_singulation_times.append(traj["compute_singulate_time"])
                if "execute_time" in traj:
                    execute_singulation_times.append(traj["execute_time"])
                waypoints, rot, free_pix = info
                if rnum == to_save_imgs_num:
                    display_singulation(waypoints, ColorImage(crop), free_pix,
                        name = "debug_imgs/rollout_imgs/r" + str(trajnum))
                singulation_attempts += 1
                if succ == "y":
                    singulation_successes += 1
            trajnum += 1
        #if grasp followed by crash
        if curr_grasp_sequence_t > 0:
            if curr_singulate_sequence not in num_singulates_to_num_grasps:
                num_singulates_to_num_grasps[curr_singulate_sequence] = []
            num_singulates_to_num_grasps[curr_singulate_sequence].append((curr_grasp_sequence_s, curr_grasp_sequence_t))

        grasps_per_rollout.append(rollout_grasps)
        singulates_per_rollout.append(rollout_singulates)

    print("SUCCESS RATES")
    percent = lambda succ, tot: "(" + str((100.0 * succ)/tot) + "%)"
    succ_rate = lambda succ, tot, name: "Succeded in " + str(succ) + " out of " + str(tot) + " " + name + " " + percent(succ, tot)
    #easy to quantify grasp success
    print(succ_rate(grasp_successes, grasp_attempts, "grasps"))
    #singulation success somewhat hard to quantify- yes if it seems to separate a pile into multiple pile
    print(succ_rate(singulation_successes, singulation_attempts, "singulations"))
    #easy to quantify color success 
    print(succ_rate(color_successes, color_attempts, "color identifications"))

    avg = lambda times: str(sum(times)/(1.0 * len(times)))

    #more quantifiable metric for singulation (see description above)
    #grasp following 0 singulation could be at start of run (some runs crash -> restart has grasps)
    #above is also the reason for ignoring singulations not followed by grasps
    print("num singulation to num successful grasps/num attempted grasps until next singulation or crash")
    print(num_singulates_to_num_grasps)
    num_singulates_to_avg_grasps = {}
    for num_singulates in num_singulates_to_num_grasps.keys():
        num_grasp = num_singulates_to_num_grasps[num_singulates]
        num_successes = [t[0] for t in num_grasp]
        num_singulates_to_avg_grasps[num_singulates] = avg(num_successes)
    print("num singulation to avg num successful grasps until next singulation or crash")
    #should add variance for each (some have a lot more data)
    print(num_singulates_to_avg_grasps)


    #just a metric of where crashes occur (might not be related to algorithm)
    if total_stopped > 0:
        print("STOPPING CONDITIONS")
        print("Out of " + str(total_stopped) + " rollouts, " +
            str(grasp_crashes) + " " + percent(grasp_crashes, total_stopped) + " ended in crashes after grasping, " +
            str(singulate_crashes) + " " + percent(singulate_crashes, total_stopped) + " ended in crashes after singulating, " +
            str(completions) + " " + percent(completions, total_stopped) + " cleared the table completely, and " +
            str(false_completions) + " " + percent(false_completions, total_stopped) + " stopped before clearing the table.")

    print("ACTION BREAKDOWN")
    print("average grasps per rollout: " + avg(grasps_per_rollout))
    print("average singulations per rollout: " + avg(singulates_per_rollout))
    print("average actions before crashs: " + avg(actions_before_crash))

    print("TIMES")
    print("average connected components time: " + avg(connected_components_times))
    print("average compute grasps time: " + avg(compute_grasps_times))
    print("average find grasps time: " + avg(find_grasps_times))
    print("average execute grasp time: " + avg(execute_grasp_times))
    print("average execute singulation time: " + avg(execute_singulation_times))
    print("average compute singulation time: " + avg(compute_singulation_times))