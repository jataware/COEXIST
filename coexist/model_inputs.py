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
