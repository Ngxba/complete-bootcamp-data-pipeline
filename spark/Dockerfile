# Custom Spark image with additional dependencies for lakehouse processing
FROM apache/spark:3.5.1-scala2.12-java17-python3-r-ubuntu

USER root

# Install additional system packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    vim \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Switch to spark user for pip installations
USER ${spark_uid}

# Install Python dependencies for data processing
RUN pip install --no-cache-dir \
    delta-spark==3.1.0 \
    kafka-python==2.0.2 \
    minio==7.2.0 \
    pandas==2.1.4 \
    pyarrow==14.0.2 \
    great-expectations==0.18.8 \
    jupyterlab==4.0.9 \
    matplotlib==3.8.2 \
    seaborn==0.13.0

# Add Delta Lake and Kafka dependencies to Spark
ENV SPARK_JARS_DIR=/opt/spark/jars
USER root
RUN curl -o ${SPARK_JARS_DIR}/delta-spark_2.12-3.1.0.jar \
    https://repo1.maven.org/maven2/io/delta/delta-spark_2.12/3.1.0/delta-spark_2.12-3.1.0.jar && \
    curl -o ${SPARK_JARS_DIR}/delta-storage-3.1.0.jar \
    https://repo1.maven.org/maven2/io/delta/delta-storage/3.1.0/delta-storage-3.1.0.jar && \
    curl -o ${SPARK_JARS_DIR}/kafka-clients-3.5.1.jar \
    https://repo1.maven.org/maven2/org/apache/kafka/kafka-clients/3.5.1/kafka-clients-3.5.1.jar && \
    curl -o ${SPARK_JARS_DIR}/spark-sql-kafka-0-10_2.12-3.5.1.jar \
    https://repo1.maven.org/maven2/org/apache/spark/spark-sql-kafka-0-10_2.12/3.5.1/spark-sql-kafka-0-10_2.12-3.5.1.jar && \
    curl -o ${SPARK_JARS_DIR}/commons-pool2-2.11.1.jar \
    https://repo1.maven.org/maven2/org/apache/commons/commons-pool2/2.11.1/commons-pool2-2.11.1.jar

# Set proper permissions
RUN chown -R ${spark_uid}:${spark_uid} ${SPARK_JARS_DIR}

USER ${spark_uid}

# Configure Spark defaults for Delta Lake
RUN echo "spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension" >> /opt/spark/conf/spark-defaults.conf && \
    echo "spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog" >> /opt/spark/conf/spark-defaults.conf && \
    echo "spark.serializer=org.apache.spark.serializer.KryoSerializer" >> /opt/spark/conf/spark-defaults.conf

WORKDIR /opt/spark/work-dir