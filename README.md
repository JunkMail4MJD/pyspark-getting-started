# pyspark-getting-started
playing with pyspark


docker pull jupyter/pyspark-notebook:spark-3.1.2

docker run -p 8888:8888 --rm --volume "`pwd`:/data" --user `id -u`:`id -g` jupyter/pyspark-notebook:spark-3.1.2
