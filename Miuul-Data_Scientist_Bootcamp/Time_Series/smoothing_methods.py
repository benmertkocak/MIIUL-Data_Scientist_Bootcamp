####################################
# Smoothing Methods (Holt-Winters) #
####################################

import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Qt5Agg")
import seaborn as sns
import matplotlib.pyplot as plt
import itertools
import statsmodels.api as sm
import statsmodels.tsa.api as smt
from sklearn.metrics import mean_absolute_error
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.holtwinters import SimpleExpSmoothing

pd.set_option('display.max_columns', None)
pd.set_option('display.width', 500)

warnings.filterwarnings('ignore')


##################
# Veri Seti
##################

# Amaç: Bir sonraki zaman periyodunda hava kirliliğinin ne olabileceğini tahmin etmek

data = sm.datasets.co2.load_pandas()

y = data.data  # bağımlı değişkenimiz

# veriler haftalık veriler hava kirliliğini aylık ölçmemiz lazım
# ilk iş aylara göre groupby

y = y["co2"].resample("MS").mean()  # aylık frekansa göre ortalama al

# eksik değerleri doldurma
y.isnull().sum()

y = y.fillna(y.bfill())  # bir sonraki değer ile doldurma

y.plot(figsize=(15, 6))
plt.show()


####################
# Holdout
####################

# k-fold yapmamamızın sebebi zaman serisi olduğu için çok karışır trend'ler, mesvsimsellik'ler vs

train = y[:"1997-12-01"]
len(train)  # 478 ay


# 1998'in ilk ayından 2001'in sonuna kadar test seti
test = y["1998-01-01":]
len(test)  # 48 ay


###################################################################
# Zaman Serisi Yapısal Analizi ( Time Series-Structural Analysis) #
###################################################################

def is_stationary(y):

    # "H0: Non-stationary"
    # "H1: Stationary

    p_value = sm.tsa.stattools.adfuller(y)[1]
    if p_value < 0.05:
        print(F"Result: Stationary (H0: non-stationary, p-value: {round(p_value, 3)})")
    else:
        print(F"Result: Non-stationary (H0: non-stationary, p-value: {round(p_value, 3)})")

is_stationary(y)  # istatiki olarak da bu serinin durağan olmadığı bilgisine erişimiş olduk

# Zaman Serisi Bileşenleri ve Durağanlık Testi
def ts_decompose(y, model="additive", stationary=False):
    result = seasonal_decompose(y, model=model)
    fig, axes = plt.subplots(4, 1, sharex=True, sharey=False)
    fig.set_figheight(10)
    fig.set_figwidth(15)

    axes[0].set_title("Decomposition for " + model + " model")
    axes[0].plot(y, 'k', label='Original ' + model)
    axes[0].legend(loc='upper left')

    axes[1].plot(result.trend, label='Trend')
    axes[1].legend(loc='upper left')

    axes[2].plot(result.seasonal, 'g', label='Seasonality & Mean: ' + str(round(result.seasonal.mean(), 4)))
    axes[2].legend(loc='upper left')

    axes[3].plot(result.resid, 'r', label='Residuals & Mean: ' + str(round(result.resid.mean(), 4)))
    axes[3].legend(loc='upper left')
    plt.show(block=True)

    if stationary:
        is_stationary(y)

ts_decompose(y, stationary=True)


##################################################
# Single Exponential Smoothing
##################################################

# SES = Level

# alpha değerine 0.5 verdik
ses_model = SimpleExpSmoothing(train).fit(smoothing_level=0.5)

# 48 adımlık tahmin yapıcaz, yukarıda test setinin boyutu 48'di (ay sayısı)i her birisi için tahmin de bulunuyoruz
y_pred = ses_model.forecast(48)

mean_absolute_error(test, y_pred)  # veri de mevsimlelik ve trend olduğu için değerler çok iyi değil


# sabit bir tahmin de bulunmuş oldukça kötü
train.plot(title="Single Exponential Smoothing")
test.plot()
y_pred.plot()
plt.show()

# yakından inceleyebilmek için
train["1985":].plot(title="Single Exponential Smoothing")
test.plot()
y_pred.plot()
plt.show()


def plot_co2(train, test, y_pred, title):
    mae = mean_absolute_error(test, y_pred)
    train["1985":].plot(legend=True, label="TRAIN", title=f"{title}, MAE: {round(mae,2)}")
    test.plot(legend=True, label="TEST", figsize=(6, 4))
    y_pred.plot(legend=True, label="PREDICTION")
    plt.show()

plot_co2(train, test, y_pred, "Single Exponential Smoothing")

ses_model.params


##############################
# Hyperparameter Optimization
##############################

def ses_optimizer(train, alphas, step=48):

    best_alpha, best_mae = None, float("inf")

    for alpha in alphas:
        ses_model = SimpleExpSmoothing(train).fit(smoothing_level=alpha)
        y_pred = ses_model.forecast(step)
        mae = mean_absolute_error(test, y_pred)

        if mae < best_mae:
            best_alpha, best_mae = alpha, mae

        print("alpha:", round(alpha, 2), "mae:", round(mae, 4))
    print("best_alpha:", round(best_alpha, 2), "best_mae:", round(best_mae, 4))
    return best_alpha, best_mae

alphas = np.arange(0.8, 1, 0.01)

# yt_sapka = a * yt-1 + (1-a)* (yt_-1)_sapka

ses_optimizer(train, alphas)

best_alpha, best_mae = ses_optimizer(train, alphas)


############################
# Final SES Model
############################

ses_model = SimpleExpSmoothing(train).fit(smoothing_level=best_alpha)
y_pred = ses_model.forecast(48)

plot_co2(train, test, y_pred, "Single Exponential Smoothing")


##################################################
# Double Exponential Smoothing (DES)
##################################################

# DES: Level (SES) + Trend

# y(t) = Level + Trend + Seasonality + Noise
# y(t) = Level * Trend * Seasonality * Noise

ts_decompose(y)

des_model = ExponentialSmoothing(train, trend="add").fit(smoothing_level=0.5,
                                                         smoothing_trend=0.5)

y_pred = des_model.forecast(48)

plot_co2(train, test, y_pred, "Double Exponential Smoothing")


#####################################
# Hyperparameter Optimization (DES) #
#####################################

def des_optimizer(train, alphas, betas, step=48):
    best_alpha, best_beta, best_mae = None, None, float("inf")
    for alpha in alphas:
        for beta in betas:
            des_model = ExponentialSmoothing(train, trend="add").fit(smoothing_level=alpha, smoothing_slope=beta)
            y_pred = des_model.forecast(step)
            mae = mean_absolute_error(test, y_pred)
            if mae < best_mae:
                best_alpha, best_beta, best_mae = alpha, beta, mae
            print("alpha:", round(alpha, 2), "beta:", round(beta, 2), "mae:", round(mae, 4))
    print("best_alpha:", round(best_alpha, 2), "best_beta:", round(best_beta, 2), "best_mae:", round(best_mae, 4))
    return best_alpha, best_beta, best_mae

alphas = np.arange(0.01, 1, 0.10)
betas = np.arange(0.01, 1, 0.10)

best_alpha, best_beta, best_mae = des_optimizer(train, alphas, betas)


############################
# Final DES Model
############################

final_des_model = ExponentialSmoothing(train, trend="add").fit(smoothing_level=best_alpha,
                                                               smoothing_slope=best_beta)

y_pred = final_des_model.forecast(48)

plot_co2(train, test, y_pred, "Double Exponential Smoothing")

# en iyi mae geldi ama hala daha dalgalanmaları yakalayamıyoruz


##################################################
# Triple Exponential Smoothing (Holt-Winters)
##################################################

# TES = SES + DES + Mevsimsellik


tes_model = ExponentialSmoothing(train,
                                 trend="add",
                                 seasonal="add",
                                 seasonal_periods=12).fit(smoothing_level=0.5,
                                                          smoothing_slope=0.5,
                                                          smoothing_seasonal=0.5)

y_pred = tes_model.forecast(48)
plot_co2(train, test, y_pred, "Triple Exponential Smoothing")


#####################################
# Hyperparameter Optimization (TES) #
#####################################

alphas = betas = gammas = np.arange(0.20, 1, 0.10)  # 3 array'e değer atadık

abg = list(itertools.product(alphas, betas, gammas))  # tuple formunda, yukarıdaki olası 3 parametrenin birliktelikler gelmiş oluyor

def tes_optimizer(train, abg, step=48):
    best_alpha, best_beta, best_gamma, best_mae = None, None, None, float("inf")
    for comb in abg:
        tes_model = ExponentialSmoothing(train, trend="add", seasonal="add", seasonal_periods=12).\
            fit(smoothing_level=comb[0], smoothing_slope=comb[1], smoothing_seasonal=comb[2])
        y_pred = tes_model.forecast(step)
        mae = mean_absolute_error(test, y_pred)
        if mae < best_mae:
            best_alpha, best_beta, best_gamma, best_mae = comb[0], comb[1], comb[2], mae
        print([round(comb[0], 2), round(comb[1], 2), round(comb[2], 2), round(mae, 2)])

    print("best_alpha:", round(best_alpha, 2), "best_beta:", round(best_beta, 2), "best_gamma:", round(best_gamma, 2),
          "best_mae:", round(best_mae, 4))

    return best_alpha, best_beta, best_gamma, best_mae

best_alpha, best_beta, best_gamma, best_mae = tes_optimizer(train, abg)


############################
# Final TES Model
############################

final_tes_model = ExponentialSmoothing(train, trend="add", seasonal="add", seasonal_periods=12).\
            fit(smoothing_level=best_alpha, smoothing_trend=best_beta, smoothing_seasonal=best_gamma)

y_pred = final_tes_model.forecast(48)

plot_co2(train, test, y_pred, "Triple Exponential Smoothing")


