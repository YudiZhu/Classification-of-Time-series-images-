import pandas as pd
import numpy as np
import glob
import matplotlib.pyplot as plt
import os
from sklearn.preprocessing import MinMaxScaler

from labels.trading_strategies import local_min_max
from transform.gramian_angular_field import GASF, GADF
from transform.recurrence_plot import RP
from transform.markov_transition_field import MTF


def data_to_labelled_img(data, column_name, label_window_size, image_window_size, image_trf_strat, 
                         num_bin=5, 
                         padding_RP=0, 
                         standardize_out_RP=False, 
                         standardize_out_GASF = False, 
                         standardize_out_GADF = False,
                         use_returns = False
                         ):
    """Turns data into series of images with labels according to a trading strategy. 
    The output images can be from multiple strategies at the same time.
    Made to suit the input of the CNN in Tensorflow.

    Parameters
    -------
        data :  pandas (time) series
            input data

        column_name : str
            name of column in df to transform

        label_window_size : int 
            the window size for data labelling (needs to be odd, should be smaller than length of series)
        
        image_window_size : int
            the window size for image creation (should be smaller than length of series, but more than half of the label window size)
            (please note that the TP transformation will result in images of size (image_window_size-1, image_window_size-1))

        image_trf_strat : string or list of strings ('GASF', 'GADF', 'RP', 'MTF')
            the image transformation strategy, either 'GASF', 'GADF', 'RP' or 'MTF'
            'GASF' - Gramian Angular Summation Field
            'GADF' - Gramian Angular Difference Field
            'RP' - Recurrence Plot
            'MTF' - Markov Transition Field.
        
        num_bin : int (default = 5)
            if image_trf_strat is 'MTF' num_bin determines the number of bins (by quantiles) to create per images in the MTF algorithm
            Default is 5.

        padding_RP :  int (default = 0)
            number of rows/columns of zero padding to be added to the right and bottom
        
        standardize_out_RP : bool (default = False)
            whether the resulting RP images should be standardized between 0 and 1 (minmax scaler)

        standardize_out_GASF : bool (default = False)
            whether the resulting GASF images should be standardized between 0 and 1 (minmax scaler)

        standardize_out_GADF : bool (default = False)
            whether the resulting GADF images should be standardized between 0 and 1 (minmax scaler)
        
        use_returns : bool (default = False)
            whether the returns should be used for image creation instead of the prices

    Returns
    -----------------------------------------
        labelled_pd : pd.dataframe
            data with new column of labels
        
        price_at_image : np.array
            the last price used to create an image (the price one would trade at given the order implied by the image)

        images : np.array
            array of transformed matrices according to transformation setting
        
        image_labels : np.array
            array of labels for each image, with one-hot encoding ("Sell", "Buy", "Hold" order for columns is default)
        
        label_names :
            dictionary linking strategy name to column index in image_labels ("Sell", "Buy", "Hold" order is default)

    """
    if image_window_size < np.ceil(label_window_size/2):
        print('image_window_size must be >= np.ceil(label_window_size/2), please choose a grater image window size.')
        return()
    else:    
        series = np.array(data[column_name].values)
        labelled_np, labelled_pd, ws, original = local_min_max(
            series, label_window_size)

        # get one-hot encoding for the labels
        dummies = pd.get_dummies(labelled_pd.Strategy)
        dummies = dummies[['Sell', 'Buy', 'Hold']]
        # for saving which column is which
        label_colnames = np.array(dummies.columns)

        if use_returns == True:
            ## if returns are used for image creation the first label we need is one step later (first return is nan)
            image_labels = np.array(dummies)[
                image_window_size:(-np.int(label_window_size/2)), :]

            price_at_image = np.array(labelled_pd.Series.values)[
                image_window_size:(-np.int(label_window_size/2))].reshape((-1,1))
        else:
            ## if prices used for image creation the first label is needed 1 step earlier
            image_labels = np.array(dummies)[
                (image_window_size-1):(-np.int(label_window_size/2)), :]
            
            price_at_image = np.array(labelled_pd.Series.values)[
                (image_window_size-1):(-np.int(label_window_size/2))].reshape((-1, 1))
        
        if use_returns == True:
            return_series = series[1:]/series[:-1] -1
            series = return_series

        # images from first datapoint to (last_idx - floor(label_window_size/2))
        if "GASF" in image_trf_strat:
            # transformation
            images_GASF,  phi_GASF, r_GASF, scaled_ts_GASF, ts_GASF = GASF(
                series[:-np.int(label_window_size/2)], image_window_size, standardize_out=standardize_out_GASF)
            images_GASF = np.array(images_GASF)
        
        if "GADF" in image_trf_strat:
            # transformation
            images_GADF,  phi_GADF, r_GADF, scaled_ts_GADF, ts_GADF = GADF(
                series[:-np.int(label_window_size/2)], image_window_size, standardize_out=standardize_out_GADF)
            images_GADF = np.array(images_GADF)

        if 'RP' in image_trf_strat:
            # transformation
            images_RP, serie_RP = RP(
                series[:-np.int(label_window_size/2)], image_window_size, padding = padding_RP, standardize_out = standardize_out_RP)
            images_RP = np.array(images_RP)

        if 'MTF' in image_trf_strat:
            #transformation
            images_MTF, binned_serie_MTF, serie_MTF = MTF(
                series[:-np.int(label_window_size/2)], window_size = image_window_size, num_bin = num_bin)
            images_MTF = np.array(images_MTF)

        if len(image_trf_strat)==0:
            print('Please define the image_trf_strat: GASF, GADF, RP or MTF')
            return()

        # Label names (as column name for image labels) 
        
        label_names = {np.int(np.argwhere(label_colnames == "Sell")) : "Sell",
                       np.int(np.argwhere(label_colnames == "Buy")) : "Buy",
                       np.int(np.argwhere(label_colnames == "Hold")) : "Hold"
                        }
        
        if (type(image_trf_strat) == list) & (len(image_trf_strat) > 1):
            
            images = []
            for trf in image_trf_strat:
                images.append(eval("images_" + trf))
            
            # channels last representation
            images = np.moveaxis(images, 0, -1)

        else:
            images = eval("images_" + image_trf_strat)

        return(labelled_pd, price_at_image, np.array(images), image_labels, label_names)

if __name__ == "__main__":
    dta = pd.DataFrame(data=np.array(np.random.normal(0, 2.3, 40)), columns=["Series"])

    labelled_pd, price_at_image, images, image_labels, label_names = data_to_labelled_img(
        data=dta, column_name="Series", label_window_size=3, image_window_size=14, image_trf_strat=["RP", "GASF", "MTF"], num_bin=4, padding_RP=1,  use_returns=False)
   
    print(price_at_image.shape)
    print(image_labels.shape)
    print(price_at_image)
    print(image_labels)
    print(label_names)
    # print(labelled_pd)
    #print(images)

    # print(image_labels)
    # print(label_names)
