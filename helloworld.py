
import os
os.environ['PYSPARK_SUBMIT_ARGS'] = '--packages=org.apache.hadoop:hadoop-common:3.1.2,org.apache.hadoop:hadoop-client:3.1.2,org.apache.hadoop:hadoop-aws:3.1.2,io.delta:delta-core_2.12:1.0.0 --conf "spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension" --conf "spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog" pyspark-shell'

import sys
!conda install --yes --prefix {sys.prefix} psycopg2-binary

# Install a pip package in the current Jupyter kernel
#import sys
#!{sys.executable} -m pip install psycopg2-binary

from pyspark import SparkContext, SparkConf, SQLContext
conf = (
    SparkConf()
    .setAppName("Spark minIO Test")
    .set("spark.hadoop.fs.s3a.endpoint", "http://minio:9000")
    .set("spark.hadoop.fs.s3a.access.key", ${env_variable})
    .set("spark.hadoop.fs.s3a.secret.key", ${env_variable})
    .set("spark.hadoop.fs.s3a.path.style.access", "true")
    .set("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
    .set("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
)
sc = SparkContext(conf=conf).getOrCreate()
sqlContext = SQLContext(sc)

df = sqlContext.read.json('s3a://landing/ids.json')
df.printSchema()

df2 = df.select("_source.*", "_type", "_index", "_id")
df2.printSchema()

from pyspark.sql.types import *
from pyspark.sql.functions import *

#Flatten array of structs and structs
def flatten(df):
   # compute Complex Fields (Lists and Structs) in Schema   
   complex_fields = dict([(field.name, field.dataType)
                             for field in df.schema.fields
                             if type(field.dataType) == ArrayType or  type(field.dataType) == StructType])
   while len(complex_fields)!=0:
      col_name=list(complex_fields.keys())[0]
      print ("Processing :"+col_name+" Type : "+str(type(complex_fields[col_name])))
    
      # if StructType then convert all sub element to columns.
      # i.e. flatten structs
      if (type(complex_fields[col_name]) == StructType):
         expanded = [col(col_name+'.'+k).alias(col_name+'_'+k) for k in [ n.name for n in  complex_fields[col_name]]]
         df=df.select("*", *expanded).drop(col_name)
    
      # if ArrayType then add the Array Elements as Rows using the explode function
      # i.e. explode Arrays
      elif (type(complex_fields[col_name]) == ArrayType):    
         df=df.withColumn(col_name,explode_outer(col_name))
    
      # recompute remaining Complex Fields in Schema       
      complex_fields = dict([(field.name, field.dataType)
                             for field in df.schema.fields
                             if type(field.dataType) == ArrayType or  type(field.dataType) == StructType])
   return df

df3=flatten(df2)
df3.printSchema()

df.count()
df2.count()
df3.count()

tags = df2.select("tags")
tags.printSchema()
tags.show()

theIPS = df2.select("ips")
theIPS.printSchema()
theIPS.show()

tags2 = df3.select("tags")
tags2.printSchema()
tags2.show()

df2.registerTempTable("ids")

counts_by_eventType = sqlContext.sql("""
    SELECT ids.source_geo.city_name, count(*) as count
    FROM ids
    group by ids.source_geo.city_name
""")
counts_by_eventType.show()

counts_by_eventType = sqlContext.sql("""
    SELECT ids.destination_geo.city_name, count(*) as count
    FROM ids
    group by ids.destination_geo.city_name
    order by count desc
""")
counts_by_eventType.show()

df2.groupby('source_ip').count().show()

counts_by_eventType = sqlContext.sql("""
    SELECT source_ip, count(*) as count
    FROM ids
    group by source_ip
    order by count desc
""")
counts_by_eventType.show()

df2.write.parquet('s3a://formated/ids')

from pyspark.sql.functions import year
from pyspark.sql.functions import month
from pyspark.sql.functions import to_date

from pyspark.sql.functions import to_timestamp,date_format
from pyspark.sql.functions import col


df2a = df2.withColumn('year',year(df2["@timestamp"]))
df2a.groupby('year').count().show()

df2a = df2a.withColumn('month',month(df2["@timestamp"]))
df2a.groupby('month').count().show()

df2a = df2a.withColumn("day", date_format(col("@timestamp"), "d"))
df2a.groupby('day').count().show()

#df2a.write.partitionBy("year","month","day").mode("overwrite").json('s3a://formated/ids.json')

df2a.write.format("delta").partitionBy("year","month","day").mode("overwrite").option("mergeSchema", "true").save('s3a://formated/ids.delta')
# append
# df.write.format("delta").mode("append").save("/delta/events")

# we can also partition the table
# df.write.format("delta").partitionBy("date").save("/delta/events")

# update
# data.write.format("delta").mode("overwrite").option("replaceWhere", "date >= '2017-01-01' AND date <= '2017-01-31'").save("/tmp/delta-table")

# by default overwrite doesn't change schema, only if option("overwriteSchema", "true") exiting
# add column automatically
# df.write.format("delta").mode("append").option("mergeSchema", "true").save("/delta/events")

import time
import pandas as pd
from sqlalchemy import create_engine
import psycopg2

pandasDF = df2a.toPandas()

conn_string = 'postgresql://dremio:dremio@10.0.187.49/dremio'

#perform to_sql test and print result
db = create_engine(conn_string)
conn = db.connect()

start_time = time.time()
pandasDF.to_sql('ids_events', con=conn, if_exists='replace', index=False)
print("to_sql duration: {} seconds".format(time.time() - start_time))

