FROM python:3.8

RUN apt-get update
RUN apt-get install -y python3-pip
RUN apt-get install -y git
RUN apt-get install -y vim

WORKDIR /
RUN git clone https://github.com/jataware/COEXIST

WORKDIR /COEXIST
RUN pip3 install -r requirements.txt
RUN mkdir /results/
RUN mkdir /inputs/

COPY coexist.py .

WORKDIR /inputs
COPY inputs/ .

WORKDIR /COEXIST
ENTRYPOINT ["python3", "coexist.py"]
CMD ["-days=30", "-out=test.csv"]
