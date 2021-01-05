#!/usr/bin/env python

import pretty_errors

# Basic packages
import numpy as np
from scipy import integrate, stats, spatial
from scipy.special import expit, binom
import pandas as pd
#import xlrd
import copy
import warnings

# Building parameter/computation graph
import inspect
from collections import OrderedDict

# OS/filesystem tools
import time
from datetime import datetime
import random
import string
import os
import shutil
import sys
import itertools

# import all the functions tat were pulled into anoter moduule
import functions as fn
import spinner as sp


'''
## Source: https://github.com/gbohner/coexist/

## MIT License

Copyright (c) 2020 Gergo Bohner

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


## COVID-19 model for policy makers in the United Kingdom

 We use an extended [SEIR model](https://en.wikipedia.org/wiki/Compartmental_models_in_epidemiology#The_SEIR_model) to capture available information both about 
the disease progression, as well as how accessible various disease states are by testing. Being tested might cause a transition in the Testing State
 the rate of such a transition depends both on the Health State as well the parameters of the test used.
 
Due to age being both an extra risk factor as well as a potential way for decision makers to clearly apply policies to only parts of the total population, 
we include it directly in our model, and most transition rates are strongly influenced by <span style="display: inline-block;background-color:#FFD4D1">Age State</span>. 

Finally, the main policy making tool as well as conundrum nowadays is the implementation of quarantining and social distancing in order to keep hospitals and medical staff under tolerable levels of pressure. We represent <span style="display: inline-block;background-color:#C2EDC0">Isolation States</span> to investigate the effects of various interventions on policy targets relating to hospitalisation rates and economic freedom, while describing the different health outcomes via the <span style="display: inline-block;background-color:#D1E2FF">Health States</span>.

 ### Health states and Disease progression
 Susceptible people may be Exposed to the virus by mixing with other infected people (E,A,I<sub>1</sub> and I<sub>2</sub>).
 They may get through the infection Asymptomatic and eventually Recover, or become symptomatic and more Infectious, spreading the disease, and potentially Dying or Recovering.
 Recovered people develop more effective antibodies against the virus, and are considered immune<sup>*</sup>.
 
     
 | State | Description | Testing |
 | ----- | ----------- | -------- |
 | S | Susceptible | Negative |
 | E | Exposed | Very weakly virus positive
 | A | Asymptomatic | Weakly virus positive
 | I<sub>1</sub> | Symptomatic early | Strongly virus positive
 | I<sub>2</sub> | Symptomatic late | Medium virus positive Weakly IgM antibody positive
 | R<sub>1</sub> | Recovered early | IgM antibody positive
 | R<sub>2</sub> | Recovered late | IgM/IgG antibody positive
 | D | COVID-related death | May be virus or antibody positive

 # Model implementation
 
 The model is governed by these two main tensors:
 - State tensor: a 4th order tensor containing axes:
     - Age groups
     - Health states
     - Isolation states
     - Testing states
     
     In our extended state tensor formulation, we also keep track of not just people currently in each state, but also people newly arriving to each state, as a large
     number of available datasets refer to "new cases" or "new hospitalisations" each day, rather than current state occupancies normally represented by ODE solutions.   
     
     
 - Dynamic state transition rate tensor
     - Rates that govern all allowed transitions between states
     - Dynamically recomputed every iteration, based on number of infected, their current social mixing and number and types of tests available, amongst other variables.
     - Briefly:
         - No transition between age groups
         - No transitions between testing states without performing a test
         - No transitions into S or out of D and R_IgG (R2) health states
     - Allowed transitions are as showcased in the model image above
     - Represented by a 7th order, sparse tensor, containing all transitions except age (unimportant due to relatively short time scales compared to coarse age grouping)


 NOTICE
 ------
 THE "MODEL IMPLEMENTATION" SECTION CONTAINS A LARGE NUMBER OF PARAMETER VALUES SET TO A DEFAULT VALUE.
 THESE ARE LARGELY INFORMED BY DATA, BUT NOT FIXED!
 THEY ARE VARIED DURING THE FITTING OF THE MODEL, ACCORDING TO HOW UNCERTAIN WE ARE IN THE PARAMETER
 
 The priors are defined below the model. Although many of our uncertain / weak assumptions are signalled by "TODO" comments, we feel that the overall 
 conclusions would not be affected by finding better parameter values, especially given our fitting and exploration approach.
 
'''

# Use available data up until this day; cutoff is important due to more recent data being less complete.
CONST_DATA_CUTOFF_DATE = "20200414"


# ### The state tensor State Dimensions: Health states (S, E and D are fixed to 1 dimension)

# number of sympyomatic infected states
nI_symp = 2 

# number of total infected states (disease stages), the +2 are Exposed and I_nonsymptomatic
nI = 2+nI_symp 

# number of recovery states (antibody development post-disease, IgM and IgG are two stages)
nR = 2 

# number of total health states, the +2: S, D are suspectible and dead
nHS = 2+nI+nR 

# Age groups (risk groups) In accordance w Imperial #13 report (0-9, 10-19, ... 70-79, 80+)
nAge = 9

# Isolation states: None/distancing, Case isolation, Hospitalised, Hospital staff
nIso = 4 

# Testing states: untested/negative, Virus positive, Antibody positive, Both positive
nTest = 4

stateTensor = np.zeros((nAge, nHS, nIso, nTest))


'''
# ### Transition rates (1 / day) 
 The full transition rate structure is an 8th order tensor, 
 mapping from any 4D state in the state tensor, to any other 4D state in the state tensor
 
 However, many of these transitions are non-sensical (ie a 3 year old cannot suddenly become 72, or a dead person be infected again), therefore during the construction of the full 
 model below, we fill in the rates on all "allowed" transitions.
 
 We attempt to do so based on existing data either describing particular rates (like COVID-related hospitalisation),
 or data that helps constrain the product or ratios of multiple rates (such as the R0, or the case fatality ratio [noting this latter depends on testing policy and test availability]).
 
 Further, to massively reduce the number of weakly constrained parameters, we will approximate many of the weakly correlated transition rates as rank 1 (uncorrelated) matrices. 
 For example the rate of hospitalisation for a patient at a given age and stage of infection will be computed as a product of two indepent rates, one based purely on the age 
 (older people are generally more at risk of hospitalisation), and the other purely on how far the patient has progressed into the disease. This allows us to estimate more of 
 required parameters from available published data.
 
 There of course still is a lot of uncertainty about how the virus behaves, and all of the data that we use is likely uncomplete and noisy. In order to better represent the things we do not
  know, we use advanced machine learning techniques, and investigate many possible scenarios (settings of parameters) and for all analyses we retain all plausible scenarios (various parameter
   settings that explain the available data well enough).
 
 Any policies we suggest for the near future are investigated for all plausible scenarios, such that decision makers know how likely each one will work as expected in these uncertain times.
 We further note that as we progress further into the pandemic, the number of plausible scenarios reduces more and more, enabling us to see the way out clearer and clearer.
'''

# Population (data from Imperial #13 ages.csv/UK): https://raw.githubusercontent.com/ImperialCollegeLondon/covid19model/master/data/ages.csv
agePopulationTotal = 1000.*np.array([8044.056,7642.473,8558.707,9295.024,8604.251,9173.465,7286.777,5830.635,3450.616])

# Currently: let's work with england population only instead of full UK, as NHS England + CHESS data is much clearer than other regions
agePopulationTotal *= 55.98/66.27 # (google england/uk population 2018, assuming age dist is similar)
agePopulationRatio = agePopulationTotal/np.sum(agePopulationTotal)

'''
 Getting infected
 ------------------
 We wish to calibrate overall infection rates to match  - previous R0 estimates, 
 - available age-attack-ratios,

 Age-dependent mixing affects state transition S -> I1 (data available eg Imperial #13 report)
 The mixing-related data is nowhere to be found!
 This is an Age x Age symmetric matrix, showing which groups mix with which other ones.
 Data from DOI: 10.1097/EDE.0000000000001047 via http://www.socialcontactdata.org/tools/ interactive tool in data folder
 This is assumed to be contacts per day (but may need to be time-rescaled)
'''

ageSocialMixingBaseline = pd.read_csv('data/socialcontactdata_UK_Mossong2008_social_contact_matrix.csv', sep=',').iloc[:,1:].values
ageSocialMixingDistancing = pd.read_csv('data/socialcontactdata_UK_Mossong2008_social_contact_matrix_with_distancing.csv', sep=',').iloc[:,1:].values

# Symmetrise these matrices (not sure why they aren't symmetric)
ageSocialMixingBaseline = (ageSocialMixingBaseline+ageSocialMixingBaseline.T)/2.
ageSocialMixingDistancing = (ageSocialMixingDistancing+ageSocialMixingDistancing.T)/2.

# For simplicity, let's assume scenario of perfect isolation in state-issued home quarantine, see commented below for alternatives
ageSocialMixingIsolation = np.zeros_like(ageSocialMixingBaseline) 

#   isolationEffectComparedToDistancing = 3. # TODO - find better numbers for proper isolation mixing estimation!
#   ageSocialMixingIsolation = ageSocialMixingBaseline/(isolationEffectComparedToDistancing * np.mean(ageSocialMixingBaseline/ageSocialMixingDistancing))



# For the S->I1 transition we also need a product mapping, as the AS->AI1 rate is variable and depend on all AI via social mixing (ages) and transmission rates (I stages)
# this vector is nI long only, calibrated together with other variables to reproduce overall R0
# These numbers should represent rate of transmission given contact [will be multiplied by social mixing matrices]
# We vary this during model fitting
transmissionInfectionStage = np.array([0.001, 0.1, 0.6, 0.5]) 

'''
 Getting Infected in the Hospital
 ---------------------------------------
 The general experience is that infections spread faster in a hospital environment, 
 we capture this intuition with an age-independent but increased "social Mixing" amongst hospital patients and staff

 TODO - This requires further data-driven calibration!

 Capture S->I1 within hospital, given the number of total infected inside hospitals
 TODO - fact check this number, atm just set based on intuition
'''

elevatedMixingRatioInHospital = 3. 

# Called "Nosocomial viral infection", some data: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5414085/
# HAP: hospital acquired pneumonia, apparently quite common
# more data: https://cmr.asm.org/content/14/3/528
# on covid-19: https://www.thelancet.com/journals/lanpub/article/PIIS2468-2667(20)30073-6/fulltext 
# "Nosocomial infection risk among health-care workers and patients has been identified as a research gap to be prioritised in the next few months by WHO."
withinHospitalSocialMixing = elevatedMixingRatioInHospital * np.sum(np.dot(agePopulationRatio, ageSocialMixingBaseline))



'''
# ## Hospitalisation and hospital staff
# 
# Disease progression in severe cases naturally leads to hospitalisation before death. 
# One of the important policy questions we wish to estimate is how many people at any one time would require a hospital bed during the treatment of their disease.
# 
# Hospitalisation is generally a simple situation modeling wise. People with either symptomatic infection (I3-...In states), or for other sicknesses (baseline hospitalisation) end up in hospital. People in S health state may return to non-hospitalised S state, however people in (informed, see later) I state generally remain in hospital until they recovered or dead.
# 
# Home quarantine / social distancing is a different situation. Unlike other reports, here we do not (yet) wish to disentagle the effects of individual quarantine operations (school closures, working from home, social distancing), but rather investigate the effects of current full lockdown (coming into effect on 24 March in the UK), versus testing-based informed individual quarantining.
# 
# Numerically:
# 
# - People in home isolation change their social mixing patterns. The overall social mixing matrix between people in no isolation and home has been estimated via the http://www.socialcontactdata.org/tools/ software, see details in the data_cleaning notebook, this will determine the S->I transition overall.
# 
# - People in hospitals (sick) dramatically reduce their contacts outside the hospital, but increase the chance of transmission within the hospitalised community. For the purpose of this simulation, hospital staff will also in effect be suspecitble to higher risk of infection due to "hospitalised" patients and they also keep their normal interaction. 
# 
# - Reported numbers regarding pressure on the health system will report both COVID-19 and non-COVID-19 patients

# Getting Hospitalised
# ---------------------------------------

# Describe the transitions to-from hospitals 
# Note that this implementation will assume that hospitalisation takes an extra day,
# due to the discrete nature of the simulation, might need to be re-thought. 
# -> if simulation of a single day is done in multiple steps (first disease progression, then potential hospitalisation),
#.    then this problem is avoided. Can do the same with testing.

# Further we assume that hospitalisation does not change health state, 
# but if happens in a non-S state, then it persists until R1 or D 
# (this may need to be relaxed for early untested I states, where the hospitalisation is not COVID-related).

# Hospitalisation mainly depends on disease severity
# Baseline hospitalisation rate (Data from Scotland: https://www.isdscotland.org/Health-Topics/Hospital-Care/Publications/Acute-Hospital-Publication/data-summary/)
#hospitalisationRateBaseline = 261278./(91.*(5.425*10**6)) # hospitalisation / (period in days * population) -> frac of pop hospitalised per day
#hospitalisationRecoveryRateBaseline = 1./4.2 # inverse of mean length of stay in days
'''

# Larger data driver approaches, with age distribution, see data_cleaning_R.ipynb for details
ageHospitalisationRateBaseline = pd.read_csv('data/clean_hosp-epis-stat-admi-summ-rep-2015-16-rep_table_6.csv', sep=',').iloc[:,-1].values
ageHospitalisationRecoveryRateBaseline = 1./pd.read_csv('data/clean_10641_LoS_age_provider_suppressed.csv', sep=',').iloc[:,-1].values

# Calculate initial hospitalisation (occupancy), that will be used to initialise the model
initBaselineHospitalOccupancyEquilibriumAgeRatio = ageHospitalisationRateBaseline/(ageHospitalisationRateBaseline+ageHospitalisationRecoveryRateBaseline)

# Take into account the NHS work-force in hospitals that for our purposes count as "hospitalised S" population, 
# also unaffected by quarantine measures
ageNhsClinicalStaffPopulationRatio = pd.read_csv('data/clean_nhsclinicalstaff.csv', sep=',').iloc[:,-1].values

# Extra rate of hospitalisation due to COVID-19 infection stages
# TODO - find / estimate data on this (unfortunately true rates are hard to get due to many unknown cases)
# Symptom to hospitalisation is 5.76 days on average (Imperial #8)

infToHospitalExtra = np.array([1e-4, 1e-3, 2e-2, 1e-2])

# We do know at least how age affects these risks:
# For calculations see data_cleaning_py.ipynb, calculations from CHESS dataset as per 05 Apr
relativeAdmissionRisk_given_COVID_by_age = np.array([-0.94886625, -0.96332087, -0.86528671, -0.79828999, -0.61535305, -0.35214767,  0.12567034,  0.85809052,  3.55950368])

riskOfAEAttandance_by_age = np.array([0.41261361, 0.31560648, 0.3843979 , 0.30475704, 0.26659415, 0.25203475, 0.24970244, 0.31549102, 0.65181376])

    
# TODO!!! - adjust disease progression transitions so that it shifts direct death probabilities to hospitalised death probabilities    

'''
 ## Disease progression
  - assumed to be strictly age and infection stage dependent distributions (progression rates), doesn't depend on other people
  - distinct states represent progression, not necessarly time, but only forward progression is allowed, and the inverse of rates represent average number of days in progression
  - there is a small chance of COVID death from every state, but we assume death is most often preceeded by hospitalisation
  - there is a chance of recovery (and becoming immunised) from every state
 
 We wish to calibrate these disease progression probabilities to adhere to observed data / earlier models
 - serial interval distribution suggests time-to-transmission of Gamma(6.5 days, 0.62) MODEL [Imperial #13]
 Symptom progression (All params with relatively wide confidence intervals)
 - infect-to-symptom onset is assumed 5 days mean MODEL [AceMod, https://arxiv.org/pdf/2003.10218.pdf]
 - symptom-to-death is 16 days DATA_WEAK [Imperial #8]
 - symptom-to-discharge is 20.5 days DATA_WEAK [Imperial #8]
 - symptom-to-hospitalisation is 5.76 days DATA_WEAK [Imperial #8]
 - hospitalisation-to-recovery is 14.51 days DATA_WEAK [Imperial #8]
 all the above in Imperial #8 is largely age dependent. Raw data available in data/ImperialReport8_subset_international_cases_2020_03_11.csv

 Based on England data (CHESS and NHS England)
 I want a way to keep this as the "average" disease progression, but modify it such that old people have less favorable outcomes (as observed)
 But correspondingly I want people at lower risk to have more favorable outcome on average
'''

# For calculations see data_cleaning_py.ipynb, calculations from NHS England dataset as per 05 Apr
relativeDeathRisk_given_COVID_by_age = np.array([-0.99742186, -0.99728639, -0.98158438, -0.9830432 , -0.82983414, -0.84039294,  0.10768979,  0.38432409,  5.13754904])

#ageRelativeDiseaseSeverity = np.array([-0.8, -0.6, -0.3, -0.3, -0.1, 0.1, 0.35, 0.4, 0.5]) # FIXED (above) - this is a guess, find data and fix
#ageRelativeRecoverySpeed = np.array([0.2]*5+[-0.1, -0.2, -0.3, -0.5]) # TODO - this is a guess, find data and fix
ageRelativeRecoverySpeed = np.array([0.]*9) # For now we make it same for everyone, makes calculations easier

# For calculations see data_cleaning_py.ipynb, calculations from NHS England dataset as per 05 Apr
caseFatalityRatioHospital_given_COVID_by_age = np.array([0.00856164, 0.03768844, 0.02321319, 0.04282494, 0.07512237, 0.12550367, 0.167096  , 0.37953452, 0.45757006])

'''
 ## Testing
 
 In this section we describe multiple types of tests (PCR, antigen and antibody), and estimate their sensitivity and specificity in different health stages. These are thought to be the same for patients of all ages, and isolation states at this time.
 
 We then model the transitions to other testing states, which are largely policy-based.
 
 To model the current data (up to 03 April 2020):
 - only PCR tests have been done in the UK
 - PCR tests are thought to be carried out almost exclusively on symptomatic patients, to determine if their symptoms are caused by SARS-CoV2 or some other infection (this helps us determine the baseline ILI symptoms in practice, to predict true negative rates of the tests given the SARS-infected vs non-SARS-infected (but ILI symptom producing) populations).
 
 One aim of this complete model is to enable policy makers to make decisions now, based on predicted test availability in the future, therefore most testing-related concerns will be hypotheticals. That said, we aim to accurately model the tests' capabilities based on extensive literature research, and also aim to bring stable policy-level outcomes despite the actual numbers may be inaccurate.
 
 Two important questions answered by integrating this section into the epidemiology model above will be:
     
     1. In what ratio we should produce antibody and antigen lateral flow immunoassay tests? They require the same production capabilities and reagents, there is a question ideally suited to the policy making level
     
     2. At what level of testing capabilities (PCR, antigen and antibody) can the country lessen the complete lockdown, without risking lives or overburdening the NHS?

 API:
 
 - trFunc_testing(stateTensor, t, policyFunc, testSpecifications, trFunc_testCapacity):
     - This is the main transition rate function, it returns transition rates from and to all testing states
 
 - policyFunc
     - Returns a testing policy about what states are tested with how many of which test
     
 - testSpecifications
     - Details the FPR/FNR of individual tests given the health state
     
 - trFunc_testCapacity(t)
     - outputs how many tests are available at time t of the different test types modelled
'''

# ### FAKE CHESS DATA

# TODO - think if we should introdce an "autopsy test" posthumously, categorising people as tested after death? 
# How is this done, is there data on its sens/spec?

# Testing capacity
# ----------------

# Assumptions about the testing capacity available at day d of the simulation 

# For PCR - we will model this (for now, for fitting we'll plug in real data!), as the sum of two sigmoids:
#   - initial stage of PHE ramping up its limited capacity (parameterised by total capacity, inflection day and slope of ramp-up)
#   - second stage of non-PHE labs joining in and ramping up capacity (this hasn't happened yet, but expected soon! same parameterisation)

# For the antigen / antibody tests we define a single sigmoidal capacity curve (starting later than PCR, but with potentially much higher total capacity)
# We further define a ratio between the production of the two, due to them requiring the same capabilities.


# FAKE data on test capacity and who got tested
# ---------------------------------------------------

df_CHESS = pd.read_csv("data/fake_CHESS.csv", sep=",", converters={'DateOfAdmission': lambda x: str(x)})

#df_CHESS.index = pd.to_datetime(df_CHESS["DateOfAdmission"].values,format="%d-%m-%Y")
df_CHESS.index = pd.to_datetime(df_CHESS["DateOfAdmission"].values,format='%Y%m%d')

# Ignore too old and too recent data points
df_CHESS = df_CHESS.sort_index().drop("DateOfAdmission", axis=1).query('20200309 <= index <= '+CONST_DATA_CUTOFF_DATE)

# Get number of tests per age group
df_CHESS_numTests = df_CHESS.loc[:,df_CHESS.columns.str.startswith("AllAdmittedPatientsTestedForCOVID19")]

# Change age groups to reflect our groupings
df_CHESS_numTests_regroup = pd.DataFrame(data = fn.regroup_by_age(
    inp = df_CHESS_numTests.to_numpy().T,
    fromAgeSplits = np.concatenate([np.array([1,5,15,25]),np.arange(45,85+1,10)]),
    toAgeSplits = np.arange(10,80+1,10)).T)

df_CHESS_numTests_regroup.index = df_CHESS_numTests.index


# ## Initialise and run the model

# Initialise state
stateTensor_init = copy.deepcopy(stateTensor)

# Populate 
stateTensor_init[:,0,0,0] = agePopulationTotal

# Move hospital staff to working in hospital
stateTensor_init[:,0,0,0] -= ageNhsClinicalStaffPopulationRatio * agePopulationTotal
stateTensor_init[:,0,3,0] += ageNhsClinicalStaffPopulationRatio * agePopulationTotal

# Move people to hospital according to baseline occupation (move only from normal people, not hospital staff!)
stateTensor_init[:,0,2,0] += initBaselineHospitalOccupancyEquilibriumAgeRatio * stateTensor_init[:,0,0,0]
stateTensor_init[:,0,0,0] -= initBaselineHospitalOccupancyEquilibriumAgeRatio * stateTensor_init[:,0,0,0]

# Infect some young adults/middle-aged people
# stateTensor_init[2:4,0,0,0] -= 1000.#/np.sum(agePopulationTotal)
# stateTensor_init[2:4,1,0,0] += 1000.#/np.sum(agePopulationTotal)
# BETTER! - People get infected by travel in early stages!


if __name__ == '__main__':

    print("\n")
    print("Running model...")

    with sp.Spinner():
        # # Takes ~2 mins on single CPU core.

        # # Build a dictionary out of arguments with defaults
        paramDict_default = fn.build_paramDict(fn.dydt_Complete)
        paramDict_default["dydt_Complete"] = fn.dydt_Complete
        paramDict_default["INIT_stateTensor_init"] = stateTensor_init

        # # Example way to set parameters conveniently, here we start quarantining early based on test results
        paramDict_current = copy.deepcopy(paramDict_default)
        paramDict_current["tStartQuarantineCaseIsolation"] = pd.to_datetime("2020-03-23", format="%Y-%m-%d")

        out1 = fn.solveSystem(stateTensor_init, total_days = 80, **paramDict_current)

    print(out1)


