# read parquet files
import pandas as pd
import pyarrow.parquet as pq
filename = "youtube_ids.parquet"
table = pq.read_table(filename)
df = table.to_pandas()
yt_ids = df['youtube_id'].tolist()
print(len(yt_ids))