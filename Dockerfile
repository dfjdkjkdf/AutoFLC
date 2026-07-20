FROM python:3.10-slim

WORKDIR /app

RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources

RUN apt-get update && apt-get install -y \
    default-jre \
    graphviz \
    build-essential \
    wget \
    fonts-wqy-zenhei \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /opt/plantuml \
    && wget https://github.com/plantuml/plantuml/releases/download/v1.2024.3/plantuml-1.2024.3.jar -O /opt/plantuml/plantuml.jar
ENV PLANTUML_JAR=/opt/plantuml/plantuml.jar

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY . .

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]