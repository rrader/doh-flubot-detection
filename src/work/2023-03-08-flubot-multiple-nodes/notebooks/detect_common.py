import os
import modin.pandas as pd
import numpy as np
import dateutil
from pathlib import Path

from sklearn.preprocessing import PolynomialFeatures, normalize, RobustScaler
from joblib import dump, load


HYPERPARAMS = [
    [0, 0, 0, 0],

    [1, 0, 0, 0],
    [2, 0, 0, 0],
    [4, 0, 0, 0],
    [6, 0, 0, 0],
    [0, 4, 0, 0],
    [1, 4, 0, 0], 
    [2, 4, 0, 0],

    [1, 0, 1, 0],
    [2, 0, 2, 0],
    [4, 0, 4, 0],
    [6, 0, 6, 0],
    [0, 4, 0, 4],
    [1, 4, 1, 4],
    [2, 4, 2, 4],
]


def enum_csv(path):
    csv_folder = Path(path)
    for p in csv_folder.glob('**/*.csv'):
        yield p


def ipfix_list_to_array(series, convert=int, limit=None):
    return series.map(
        lambda val: np.array([
            convert(x) 
            for x in val.strip("[]").split("|") if x != ''
        ])[:limit]
    )


def direction_sizes_filter(direction):
    return lambda x: np.array([
        sz
        for sz, dir_, in zip(x[0], x[1])
        if dir_ == direction
    ])


def millis_diffs(arr, pkts_limit):  # Zhan 2022 discards total bytes but uses Time intervals
    times = ipfix_list_to_array(arr, dateutil.parser.parse, limit=pkts_limit+1)
    return times.apply(lambda arr: np.array([(b - a).total_seconds() * 1000 for a, b in zip(arr, arr[1:])]))


def get_doh_ips(path_doh_ips):
    doh_ips_df = pd.read_csv(path_doh_ips)
    return doh_ips_df.iloc[:,0].to_list()


def stat_funcs(skip, weighted_num):
    def weights(a):
        n = len(a)
        zeros = min(skip, n)
        weights = min(n - zeros, weighted_num + 1)
        ones = max(n - zeros - weights, 0)
        return np.concatenate([
            np.zeros(zeros),
            np.linspace(0.1, 1, weights),
            np.ones(ones),
        ])

    def var(a__mean):
        a, average = np.array(a__mean[0]), a__mean[1]
        w = weights(a)
        return np.average((a-average)**2, weights=w) if np.sum(w) > 0 else 0.0

    def mean(a):
        w = weights(a)
        return np.average(a, weights=w) if np.sum(w) > 0 else 0.0
    return mean, var


def fields_stats(dfx, fields, skip=0, weighted_num=0):
    mean, var = stat_funcs(skip, weighted_num)

    for field in fields:
        dfx[f"{field}_mean"] = dfx[field].apply(mean)
        dfx[f"{field}_var"] = dfx[[field, f"{field}_mean"]].apply(var, axis=1)
        dfx[f"{field}_stddev"] = np.sqrt(dfx[f"{field}_var"])
        
    return dfx


def filter_significant_flows(dfx):
    return dfx[
        (dfx["uint32 PACKETS"] > 2) &
        (dfx["uint32 PACKETS_REV"] > 2) &
        (dfx["uint16* PPI_PKT_LENGTHS"].str.len() > 2) &
        (dfx["uint16* PPI_PKT_LENGTHS_1"].str.len() > 2) &
        (dfx["uint16* PPI_PKT_LENGTHS_-1"].str.len() > 2)
    ]


class CacheableProcessing:
    def __init__(self, len_pkts_limit, times_pkts_limit, doh_ips=None):
        self._len_pkts_limit = len_pkts_limit
        self._times_pkts_limit = times_pkts_limit
        self._doh_ips = doh_ips

        self._is_labeled = False
        self._is_filtered = False
        self._is_processed = False
    
    def _reversed_rows(self, dfx):
        reversed_rows = dfx["uint16 SRC_PORT"] < 1024
        dfx = dfx[~reversed_rows]  # ignore reversed rows
        return dfx
    
    def _filter_out_icmp(self, dfx):
        return dfx[(dfx["uint8 PROTOCOL"] != 58) & (dfx["uint8 PROTOCOL"] != 1)]  # no ICMPv6 and ICMP

    def _filter_443(self, dfx):
        dfx = dfx[dfx["uint16 DST_PORT"] == 443]  # filter HTTPS
        self._is_filtered = True
        return dfx

    def clean(self, df):
        dfx = df.copy()
        dfx = self._filter_out_icmp(dfx)
        dfx = self._reversed_rows(dfx)
        return dfx
    
    def _pkt_lengths(self, dfx, pkts_limit):
        dfx["uint16* PPI_PKT_LENGTHS"] = ipfix_list_to_array(dfx["uint16* PPI_PKT_LENGTHS"], limit=pkts_limit)
        dfx["int8* PPI_PKT_DIRECTIONS"] = ipfix_list_to_array(dfx["int8* PPI_PKT_DIRECTIONS"], limit=pkts_limit)

        dfx["uint16* PPI_PKT_LENGTHS_1"] = dfx[["uint16* PPI_PKT_LENGTHS", "int8* PPI_PKT_DIRECTIONS"]].apply(
            direction_sizes_filter(1), axis=1
        )
        dfx["uint16* PPI_PKT_LENGTHS_-1"] = dfx[["uint16* PPI_PKT_LENGTHS", "int8* PPI_PKT_DIRECTIONS"]].apply(
            direction_sizes_filter(-1), axis=1
        )
        return dfx

    def _pkt_times(self, dfx, pkts_limit):
        dfx["PPI_PKT_INTERVALS"] = millis_diffs(dfx["time* PPI_PKT_TIMES"], pkts_limit)

        dfx["PPI_PKT_INTERVALS_1"] = dfx[["PPI_PKT_INTERVALS", "int8* PPI_PKT_DIRECTIONS"]].apply(
            direction_sizes_filter(1), axis=1
        )
        dfx["PPI_PKT_INTERVALS-1"] = dfx[["PPI_PKT_INTERVALS", "int8* PPI_PKT_DIRECTIONS"]].apply(
            direction_sizes_filter(-1), axis=1
        )
        return dfx

    def _label_dataset(self, dfx):
        dfx["IsDoH"] = (dfx["ipaddr DST_IP"].isin(self._doh_ips) & (dfx["uint16 DST_PORT"] == 443))
        self._is_labeled = True
        return dfx

    def load(self, stored_df_file):
        if stored_df_file and os.path.exists(stored_df_file):
            self._df = pd.read_json(stored_df_file).sort_index()
            self._is_processed = True
            return True
        return False

    def store(self, stored_df_file):
        self._df.to_json(stored_df_file)

    def process(self, df, stored_df_file):
        if not self.load(stored_df_file):
            dfx = df.copy()
            dfx = self._reversed_rows(dfx)
            dfx = self._filter_443(dfx)
            dfx = self._pkt_lengths(dfx, self._len_pkts_limit)
            dfx = self._pkt_times(dfx, self._times_pkts_limit)

            if self._doh_ips is not None:
                dfx = self._label_dataset(dfx)

            # dfx = dfx.reset_index(drop=True)
            self._df = dfx
            self._is_processed = True
            self.store(stored_df_file)
        return self._df


class PreProcessing:
    def __init__(self, norm=True, l_skip=0, l_weights=0, t_skip=0, t_weights=0):
        self._df = None
        self._df_f = None
        self._df_l = None
        self._is_processed = False

        self._do_norm = norm
        self._scaler = None

        self._l_skip = l_skip
        self._l_weights = l_weights
        self._t_skip = t_skip
        self._t_weights = t_weights

    def _feature_fields(self):
        base_feature_fields = [
            "uint16* PPI_PKT_LENGTHS",
            "uint16* PPI_PKT_LENGTHS_1",
            "uint16* PPI_PKT_LENGTHS_-1",
        ]
        base_feature_fields += [  # interval features
            "PPI_PKT_INTERVALS",
            "PPI_PKT_INTERVALS_1",
            "PPI_PKT_INTERVALS-1",
        ]

        base_feature_fields_stats = [f"{field}{suffix}" for field in base_feature_fields for suffix in ["_stddev", "_mean", "_var"]]
        add_feature_fields = []

        feature_fields = base_feature_fields_stats + add_feature_fields
        return feature_fields

    @property
    def feature_fields(self):
        return self._feature_fields()

    def load(self, stored_df_file):
        if stored_df_file and os.path.exists(stored_df_file):
            self._df = pd.read_json(stored_df_file).sort_index()
            self._df_f = pd.read_json(stored_df_file + '.features').sort_index()
            self._df_l = pd.read_json(stored_df_file + '.labels').sort_index()
            self._is_processed = True
            return True
        return False
    
    def store(self, stored_df_file):
        self._df.to_json(stored_df_file)
        self._df_f.to_json(stored_df_file + '.features')
        self._df_l.to_json(stored_df_file + '.labels')

    def _filter_empty(self, dfx):
        return dfx[
            (dfx["uint32 PACKETS"] > 0) &
            (dfx["uint32 PACKETS_REV"] > 0) &
            (dfx["uint16* PPI_PKT_LENGTHS"].str.len() > 0) &
            (dfx["uint16* PPI_PKT_LENGTHS_1"].str.len() > 0) &
            (dfx["uint16* PPI_PKT_LENGTHS_-1"].str.len() > 0)
        ]

    def _norm(self, dfx, fit_new_scaler=True):
        if self._do_norm:
            feature_fields_stats = self._feature_fields()

            if fit_new_scaler:
                scaler = RobustScaler(
                    unit_variance=False
                ).fit(dfx[feature_fields_stats])
                self._scaler = scaler
            else:
                scaler = self._scaler
                assert self._scaler is not None

            dfx[feature_fields_stats] = scaler.transform(dfx[feature_fields_stats])
        return dfx

    def store_scaler(self, stored_file):
        dump(self._scaler, stored_file)

    def load_scaler(self, stored_file):
        self._scaler = load(stored_file)

    def _split_features_label(self, dfx):
        feature_fields_stats = self._feature_fields()

        dfx_features = dfx[feature_fields_stats].copy()
        dfx_labels = None
        if 'IsDoH' in dfx.columns:
            dfx_labels = dfx[["IsDoH"]].copy()
        return dfx, dfx_features, dfx_labels

    def process(self, df, stored_df_file, fit_new_scaler=True):
        if not self.load(stored_df_file):
            dfx = df.copy()

            dfx = fields_stats(
                dfx, 
                ["uint16* PPI_PKT_LENGTHS", "uint16* PPI_PKT_LENGTHS_1", "uint16* PPI_PKT_LENGTHS_-1"],
                self._l_skip,
                self._l_weights,
            )

            dfx = fields_stats(
                dfx, 
                ["PPI_PKT_INTERVALS", "PPI_PKT_INTERVALS_1", "PPI_PKT_INTERVALS-1"],
                self._t_skip,
                self._t_weights,
            )

            dfx = self._filter_empty(dfx)
            dfx = self._norm(dfx, fit_new_scaler)

            df, df_f, df_l = self._split_features_label(dfx)
            self._df = df
            self._df_f = df_f
            self._df_l = df_l
            self._is_processed = True
            self.store(stored_df_file)
        return self._df, self._df_f, self._df_l
