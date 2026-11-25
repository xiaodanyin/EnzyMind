import pandas as pd
import os


select_df = pd.DataFrame()
file_list = os.listdir('../../enzyme_agent/data/ecnumber_prediction_data/clean_test_set')
for file in file_list:
    df = pd.read_csv(os.path.join('../../enzyme_agent/data/ecnumber_prediction_data/clean_test_set', file), sep='\t')
    sub_df = df.sample(6, random_state=42)
    select_df = pd.concat([select_df, sub_df], ignore_index=True)

select_df = select_df.drop_duplicates(ignore_index=True)
select_df.to_csv('../../enzyme_agent/data/ecnumber_prediction_data/clean_test_set/test_sequence.csv', index=False)