from snorkel.slicing import SFApplier
from functools import reduce
from IPython import embed

from ir_slices.data_processors import processors
from ir_slices.slice_functions import slicing_functions, all_instances

import numpy as np
import scipy.stats

import pandas as pd
import argparse


pd.set_option('display.max_columns', None)

def confidence_interval(data, confidence=0.95):
    a = 1.0 * np.array(data)
    n = len(a)
    m, se = np.mean(a), scipy.stats.sem(a)
    h = se * scipy.stats.t.ppf((1 + confidence) / 2., n-1)
    return h

def main():

    parser = argparse.ArgumentParser()

    ## Required parameters
    parser.add_argument("--data_dir", default=None, type=str, required=True,
                        help="The input data dir. Should contain the .tsv files (or other data files) for the task.")
    parser.add_argument("--task_name", default=None, type=str, required=True,
                        help="The name of the task to train selected in the list: " + ", ".join(processors.keys()))
    parser.add_argument("--eval_metrics_files", default="", type=str,
                        help="The files with the metrics (e.g. AP, nDCG) for each query, separated by ;")
    parser.add_argument("--eval_models", default="", type=str,
                        help="The names of the models separated by ;")

    args = parser.parse_args()

    eval_metrics = ['AP']
    dfs = []
    for model_eval_file, model_name in zip(args.eval_metrics_files.split(";"),
                                           args.eval_models.split(";")):
        df_eval = pd.read_csv(model_eval_file, names=eval_metrics)

        processor = processors[args.task_name]()
        examples = processor.get_dev_examples(args.data_dir)

        per_slice_results = []
        for slice_function in slicing_functions[args.task_name] + [all_instances]:
            slice = [slice_function(example) for example in examples]
            df_eval[slice_function.name] = slice
            for metric in eval_metrics:
                per_slice_results.append([args.task_name, model_name, slice_function.name, metric,\
                                          df_eval[df_eval[slice_function.name]][metric].mean(),
                                          df_eval[df_eval[slice_function.name]][metric],
                                          confidence_interval(df_eval[df_eval[slice_function.name]][metric]),
                                          df_eval[df_eval[slice_function.name]].shape[0]/df_eval.shape[0],
                                          df_eval[df_eval[slice_function.name]].shape[0]])
        per_slice_results = pd.DataFrame(per_slice_results,
                                        columns=["task", "model", "slice", "metric",
                                                 "value", "all_values", "ci",
                                                 "%", "N"])
        dfs.append(per_slice_results)
    all_dfs = pd.concat(dfs)
    print(all_dfs.sort_values(["model", "value"]))
    all_dfs.sort_values(["model", "value"]).to_csv("../../tmp/res_"+args.task_name)

    df_final = reduce(lambda left, right: pd.merge(left, right, on='slice'), dfs)
    df_final['delta'] = df_final['value_y']-df_final['value_x']
    df_final['p_value'] = df_final.apply(lambda x,f=scipy.stats.ttest_ind:
                                         f(x['all_values_y'], x['all_values_x'])[1], axis=1)
    df_final['p_value<0.05'] = df_final['p_value']<0.05
    df_final['p_value<0.01'] = df_final['p_value']<0.01
    df_final.to_csv("../../tmp/delta_res_" + args.task_name)

if __name__ == "__main__":
    main()
