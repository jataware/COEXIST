## COVID SEIR Model:
This repository, an abstraction of the UK-specific [COEXIST Model](https://github.com/gbohner/coexist), enables users to choose any geographic region and run an SEIR simulation. It is purpose-built to predict health state progression for COVID, but can be updated for different viruses. 

To run the COVID model, the user must have access to basic virus and hospitalization data for their geographic region.  For a new virus, an expert level of knowledge is required to properly tune the input parameters. 

See the COEXIST license agreement at the end of this README.


## Contents
1. [Motivation](#motivation)
2. [COEXIST Model Overview](#coexist-model-overview)
3. [Input Parameters](#input-parameters)
4. [Quick Start](#quick-start)
5. [Output Description](#output-description)
7. [COEXIST License](#coexist-license)

## Motivation
The motivation behind this project is to abstract the UK COEXIST model to provide a robust and geographic-agnostic COVID SEIR model to analysts. The model is abstracted by:

  - Allowing the model to run for any geopolitical area of interest
  - Identifing and classifing input parameters by source. For instance, some parameters such as population are readily available; while others such as baseline hospital admission rates may require expert input to come to reasonable estimations.
  - Reducing the exposed input parameters to modelers to allow for easier model builds and exploration

## COEXIST Model Overview
COEXIST (COVID Exit Strategy) was developed to inform COVID-related policy decisions for the UK government by investigating the effects of testing protocols, social distancing, and quarantining.  The model was purpose-built for the UK with extensive supporting data provided by the National Health Service. Note, the CHESS data referenced in the repository is protected and unavailable. Our code obviates the need for this CHESS data by manually passing in testing data.

For an extensive model description as well as acces to the well-documented code, see the [COEXIST Model](https://github.com/gbohner/coexist) repository.

### States and Transistions:

<center>
<img src="images/dynamicalModel.png" width="700">
</center>

### Health State Descriptions:
<center> 

| State | Description | Test outcome |
| ----- | ----------- | -------- |
| S | Susceptible | Negative |
| E | Exposed | Very weakly virus positive
| A | Asymptomatic | Weakly virus positive
| I<sub>1</sub> | Symptomatic early | Strongly virus positive
| I<sub>2</sub> | Symptomatic late | Medium virus positive <br>Weakly IgM antibody positive
| R<sub>1</sub> | Recovered early | IgM antibody positive
| R<sub>2</sub> | Recovered late | IgM+IgG antibody positive
| D | COVID-related death | May be virus or antibody positive

**Table 1** - Description of Health States and test outcomes
</center>

## Input Parameters
Our variant of the COEXIST model reduces the initial data collection/cleaning requirements by: 
  
1. aggregating applicable inputs to a single input,
2. leveraging subject matter expertise to estimate parameters assumed to inaccesible to the average general modeler, and
3. only exposing parameters that a general modeler would reasonably have access to for their chosen geography.

We seperate the input parameter requirements into three broad categories: 1) SME parameters, 2) General Modeler Parameters, and 3) Social Mixing Matrices where each category has its own distinct groupings. Below is a description of each required parameter for the three categories.

### SME Parameter Category:
SME parameters are assumed to require subject matter expertise for detailed baseline hospital and COVID data for the geographic area of interest. Parameters are updated in the `sme_input.json` file [HERE](https://github.com/jataware/COEXIST/blob/main/inputs/sme_input.json). For practical steps in populating the `sme_input.json` and running the model, see the [Quick Start](#quick-start) section. The two SME Parameter Groups are:

  1. **Age-Group Parameters**. These are baseline, not COVID-related hospital data where each parameter is binned into the following age blocks according to the descriptions below:

  **Age-Groups**:  "0-9", "10-19", "20-29",  "30-39",  "40-49", "50-59", "60-69", "70-79", "80+"


  If your data does not match these age groupings, you can either interpolate your data to fit these blocks or rely on the built in helper function `regroup_by_age` in the model that re-allocates your data into the appropriate bins. Care should be taken when relying on the function and binning results should be verified.

  <center>

  | Parameter | Description             |
  | --------- | ----------------------- |
  | "agePopulationTotal" | By age-group, the total population in that age-group |
  | "yearly\_baseline\_admissions"| By age-group, the total number of patients admitted to the hospital  over the course of a year 
  | "ageHospitalMeanLengthOfStay" | By age-group, a patient’s average length of stay in the hospital 
  | "ageNhsClinicalStaffPopulationRatio" | By age-group, the percentage of that age-group that are hospital staff
  | "riskOfAEAttandance_by_age" | By age-group, the number of emergency hospital admissions divided by the age-group population total
  </center>


2. **Health-State Parameters**. COVID-related data. Each value is binned sequentially into the following Health States:
 
  [“E”, “A”, “I1”, “I2”] which translates to: 

 [“Very weakly virus positive”, “Weakly virus positive”, “Strongly virus positive”, “Medium virus positive / Weakly IgM antibody positive”]

   
  In these Health States someone is infected and can therefore possibly be hospitalized or infect someone else they contact.

  <center>

  | Parameter    | Description             |
  | ------------ | ----------------------- |
  | "transmissionInfectionStage"|The rate of transmission given contact and your current Health State. For example, if transmissionInfectionStage = [0.001, 0.1, 0.6, 0.5] and you are Asymptomatic there is a 10% chance you will infect someone you contact; a 60% chance if you are in the “Early/High Viral load” health state.|
  | "infToHospitalExtra" | Extra rate of hospitalization above baseline given current Health State. For example if infToHospitalExtra = [1e-4, 1e-3, 2e-2, 1e-2] and you are `Asymptomatic` ("A") there is a 0.10% chance you will be admitted to the hospital; a 2.0% chance if you are in the `Early/High Viral load` ("I2") health state. Note: This is difficult to approximate due to the high number of unknown cases.
  
  </center>
    - Note that these parameters are _independent_ of age


### General Modeler Parameter Category:
General Modeler Parameters are assumed to be readily available and open to the public for the geographic area of interest. Parameters are updated in the `user_input.json` file [HERE](https://github.com/jataware/COEXIST/blob/main/inputs/user_input.json). For practical steps in populating the `user_input.json` and running the model, see the [Quick Start](#quick-start) section. The three General Modeler Parameter Groups are:

  1. **Age-Group Parameters**. Each parameter is binned into the following age blocks according to the descriptions below:

  **Age-Groups**:  "0-9", "10-19", "20-29",  "30-39",  "40-49", "50-59", "60-69", "70-79", "80+"


  If your data does not match these age groupings, you can either interpolate your data to fit these blocks or rely on the built in helper function `regroup_by_age` in the model that re-allocates your data into the appropriate bins. Care should be taken when relying on the function and binning results should be verified.

  <center>

  | Parameter | Description             |
  | --------- | ----------------------- |
  | "percent_admitted" | By age-group, the percent of patients admitted to the hospital due to COVID |
  | "deaths\_by\_age" | By age-group, the total count of COVID deaths
  | "ageHospitalMeanLengthOfStay" | By age-group, a patient’s average length of stay in the hospital 
  | "percent\_not\_isolating" | By age-group, the percent of people not adhering to isolation requirements

  </center>


2. **Start/Stop Parameters**. Set the start date for the simulation, filter data, and  choose the start and stop dates for the available policies.

  **NOTE**: All dates are formatted **`YYYY-MM-DD`** unless otherwise noted.


  <center>

  | Parameter    | Description             |
  | ------------ | ----------------------- |
  | "testingStartDate"| Datetime to start the simulation
  | "tStartSocialDistancing"| Datetime to start Social Distancing Policy
  | "tStopSocialDistancing"| Datetime to stop Social Distancing Policy
  | "tStartImmunityPassports"| Datetime to start Immunity Passport Policy
  | "tStopImmunityPassports" | Datetime to stop Immunity Passport Policy
  | "tStartQuarantineCaseIsolation" | Datetime to start Quarantine Policy
  | "tStopQuarantineCaseIsolation" | Datetime to stop Quarantine Policy
  | "testingStartDate"| Datetime to begin simulation
  | "CONST\_DATA\_START\_DATE" | Start data for data ingestion; used to filter out data before this date if the data is of poor quality. **Format `YYYYMMDD`**
  | "CONST\_DATA\_CUTOFF\_DATE" | Stop data for data ingestion; used to filter out data after this date if the data is of poor quality. **Format `YYYYMMDD`**


3. **Policy Parameter**. A parameter set by government policy.

  <center>
  
  | Parameter | Description             |
  | --------- | ----------------------- |
  | "nDaysInHomeIsolation" | Number of days that exposed or infected people are required to isolate |
  </center>

### Social Mixing Matricies Category:
Social Mixing Matricies estimate, by age group, the average number of daily social interactions someone has with other people. There are two variants: 1) `social_mixing_BASELINE` which reflects non-COVID or "normal" social mixing ([example](https://github.com/jataware/COEXIST/blob/main/inputs/social_mixing_BASELINE.json)), and 2) `social_mixing_DISTANCE` which reflects a reduced number of interactions due to social mixing policies ([example](https://github.com/jataware/COEXIST/blob/main/inputs/social_mixing_DISTANCE.json)).

The examples provided are an average of several social mixing matrices from survey data available [HERE](http://www.socialcontactdata.org/tools/). When using the tool, the age-groups need to be defined by the 10-year blocks as shiwn in the other input parameter categories. In the `mixing` directory the notebook `mixing_comparison.ipynb` has examples on how to compare and average social mixing interactions for different countries.

## Quick Start:

### 1. Run from published Docker Image:
NOTE: The data in this image is for the UK example. To change the input parameters you will need to build your own docker image or run the model locally. 

1. run `docker run --rm jataware/coexist -days=<numberOfSimDays> -out=<outfile>.csv` to run your model instantiation
   where:
  
	- `-days` = number of days to run simulation
	- `-out` = name of output `.csv` file

### 2. Build your own Docker Image:
To build a docker image and run a container:

1. run `git clone https://github.com/jataware/COEXIST.git` 
2. run `cd your/local/folder/COEXIST/inputs` 
3. In the inputs directory, update the `sme_input.json` and `user_input.json` files as described above
4. run `cd ~/COEXIST`
5. Verify `Dockerfile` is in your current working directory
6. Launch Docker from command line or the Docker app
7. run `docker  build . -t coexist` to build an image named `coexist`
8. run `docker run --rm coexist -days=<numberOfSimDays> -out=<outfile>.csv` to run your model instantiation
   where:
  
	- `-days` = number of days to run simulation
	- `-out` = name of output `.csv` file


### 3. Local Run (no Docker needed):

1. Clone the [COEXIST](https://github.com/jataware/COEXIST) repository to `your/local/folder`.
2. run `cd ~/COEXIST && pip install -r requirements.txt`
3. run `cd ~/inputs`
4. In the inputs directory, update the `sme_input.json` and `user_input.json` files as described above
5. run `cd ~/COEXIST`
6. run `python3 coexist.py -days=180 -out=results.csv` 

   where:
  
	- `-days` = number of days to run simulation
	- `-out` = name of output `.csv` file
	

## Output Description:
When the model run is complete, your `<outfile>.csv` file is written to `~/results/<outfile>.csv`. The output is a csv file with the following columns:

  - `timestamp`: number of days (in YYYY-MM-DD format) from your simulation `testingStartDate` as defined in the `user_input.json`
  - `simDay`: integer number of days from your simulation `testingStartDate` as defined in the `user_input.json`
  - `arrivalType`: the method of Health State count for each day. Options include:
  
		 -  `new`: Health States reflect daily count of new arrivals
		 -  `current`: Health States reflect total daily count of people in the state
  - `ageGroup`: 10-year age-group blocks
  - `healthState`: the Health State 
  - `value`: The daily count of people for the row's simulation day, arrival type, age group, and health state

Example slice of the output dataframe on the first simulation day (initial) for the 0-9 Age Group :
<center>

| timestamp  | simDay | arrivalType | ageGroup | healthState | value |
| ---------- | -------|----------- | -------- | ----------- | ------|
| 2020-12-15 | 1 | current | 0-9 |susceptible| 6,795,024 |
| 2020-12-15 | 1 | current | 0-9 |exposed | 0.0 |
| 2020-12-15 | 1 | current | 0-9 |asymptomatic | 0.0 |
| 2020-12-15 | 1 | current | 0-9 |infected1 | 0.0 |
| 2020-12-15 | 1 | current | 0-9 |infected2 | 0.0 |
| 2020-12-15 | 1 | current | 0-9 |recovered1 | 0.0 |
| 2020-12-15 | 1 | current | 0-9 |recovered2 | 0.0 |
| 2020-12-15 | 1 | current | 0-9 |deceased | 0.0 |
</center>

**There is a jupyter notebook `plot_coexist_results` that reads in your `<output>.csv` and has example plots of the data.**

 

## COEXIST License:
MIT License, Copyright (c) 2020 Gergo Bohner

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
