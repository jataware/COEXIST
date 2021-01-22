FROM python:3.8

RUN apt-get update
RUN apt-get install python3-pip -y
RUN apt-get install -y git

WORKDIR /

RUN git clone https://github.com/jataware/COEXIST

WORKDIR /COEXIST

RUN pip3 install -r requirements.txt

COPY coexist.py .

RUN mkdir /results/
RUN mkdir /inputs/

WORKDIR /inputs
COPY inputs/sme_input.json .
COPY inputs/user_input.json .
COPY inputs/social_mixing_BASELINE.csv .
COPY inputs/social_mixing_DISTANCE.csv .

WORKDIR /COEXIST

ENTRYPOINT ["python3", "coexist.py"]
CMD ["-days=30", "-out=test.csv"]

