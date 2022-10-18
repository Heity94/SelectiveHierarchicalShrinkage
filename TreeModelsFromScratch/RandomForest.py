from DecisionTree import DecisionTree
import numpy as np
import pandas as pd
from collections import Counter
from warnings import warn, catch_warnings, simplefilter
from sklearn.metrics import mean_squared_error, accuracy_score
import numbers

class RandomForest:
    def __init__(self,
                 n_trees=10,
                 max_depth=None,
                 min_samples_split=2,
                 min_samples_leaf=1,
                 n_feature=None,
                 bootstrap=True,
                 oob=True,
                 criterion="gini",
                 treetype="classification",
                 HShrinkage=False,
                 HS_lambda=0,
                 k=None,
                 random_state=None):
        self.n_trees = n_trees
        self.max_depth=max_depth
        self.min_samples_split=min_samples_split
        self.min_samples_leaf = min_samples_leaf  # Still need to be implemented
        self.n_features=n_feature
        self.bootstrap=bootstrap
        self.oob = oob
        self.criterion = criterion
        self.k = k
        self.HShrinkage = HShrinkage
        self.HS_lambda = HS_lambda
        self.treetype = treetype
        self.random_state = self._check_random_state(random_state)
        #self.random_state = np.random.default_rng(random_state)
        self.trees = []
        self.feature_names = None

    def _check_random_state(self, seed):
        if isinstance(seed, numbers.Integral):
            return np.random.RandomState(seed)
            #return np.random.default_rng(seed)
        if isinstance(seed, np.random.RandomState):
            return seed

    def fit(self, X, y):
        self.trees = []

        if isinstance(X, pd.DataFrame):
            self.feature_names = X.columns
            X = X.values

        #MAX_INT = np.iinfo(np.int32).max

        #Create random seeds for each tree in the forest
        #seed_list = self.random_state.randint(MAX_INT, size=self.n_trees)

        #Create forest
        #for _, seed in zip(range(self.n_trees), seed_list):
        for _ in range(self.n_trees):

            #Instantiate tree
            tree = DecisionTree(max_depth=self.max_depth,
                                min_samples_split=self.min_samples_split,
                                min_samples_leaf=self.min_samples_leaf,
                                n_features=self.n_features,
                                criterion=self.criterion,
                                treetype=self.treetype,
                                feature_names=self.feature_names,
                                HShrinkage=self.HShrinkage,
                                HS_lambda=self.HS_lambda,
                                k=self.k,
                                random_state=self.random_state)

            #Draw bootstrap samples (inbag)
            X_inbag, y_inbag, idxs_inbag = self._bootstrap_samples(
                X, y, self.bootstrap, self.random_state) #self._check_random_state(seed))

            # Fit tree using inbag samples
            tree.fit(X_inbag, y_inbag)
            self.trees.append(tree) #Add tree to forest

            # Draw oob samples (which have not been used for training) and predict oob observations
            if self.oob:
                n_samples = X.shape[0]
                tree.oob_preds = np.full(n_samples, np.nan)#np.zeros(n_samples, dtype=np.float64)
                #n_oob_pred = np.zeros(n_samples, dtype=np.int64)

                X_oob, y_oob, idxs_oob = self._oob_samples(X, y, idxs_inbag)

                tree.oob_preds[idxs_oob] = tree.predict(X_oob)

        # Calculate oob_score for all trees within forest
        if self.oob:

            with catch_warnings():
                simplefilter("ignore", category=RuntimeWarning)

                # Get mean value for each oob prediction ignoring the nan values (nan will be kept only if there is no prediction from none of the trees in the forest)
                self.oob_preds_forest = np.nanmean([tree.oob_preds for tree in self.trees], axis=0)
            y_test_oob = y.copy()

            # Check if there are any y obs where there is no oob prediction:
            if np.isnan(self.oob_preds_forest).any():

                # identify index of all nan values (where no oob pred is found)
                nan_indxs = np.argwhere(np.isnan(self.oob_preds_forest))

                #Throw UserWarning of how many values did not have an oob prediction
                message = """{} out of {} samples do not have OOB scores. This probably means too few trees were used to compute any reliable OOB estimates. These samples were dropped before computing the oob_score""".format(len(nan_indxs), len(y))
                warn(message)

                # drop these NaN values from X_oob_preds and y_test_oob
                mask = np.ones(self.oob_preds_forest.shape[0], dtype=bool)
                mask[nan_indxs] = False
                self.oob_preds_forest = self.oob_preds_forest[mask]
                y_test_oob = y[mask]

            # calculate oob_score and store score as class attribute
            if self.treetype=="classification":
                self.oob_preds_forest = self.oob_preds_forest.round(0) #round to full number 0 or 1
                self.oob_score = accuracy_score(y_test_oob, self.oob_preds_forest) #accuracy
            elif self.treetype=="regression":
                self.oob_score = mean_squared_error(y_test_oob, self.oob_preds_forest, squared=False) #RMSE

    def _bootstrap_samples(self, X, y, bootstrap, random_state):

        if bootstrap:
            n_samples = X.shape[0]
            idxs_inbag = random_state.choice(n_samples, n_samples, replace=True)
            return X[idxs_inbag], y[idxs_inbag], idxs_inbag
        else:
            return X, y, np.arange(X.shape[0])

    def _oob_samples(self, X, y, idxs_inbag):
        mask = np.ones(X.shape[0], dtype=bool)
        mask[idxs_inbag] = False
        X_oob = X[mask]
        y_oob = y[mask]
        idxs_oob = mask.nonzero()
        return X_oob, y_oob, idxs_oob

    def _most_common_label(self, y):
        counter = Counter(y)
        most_common = counter.most_common(1)[0][0]
        return most_common

    def predict(self, X):
        if isinstance(X, pd.DataFrame):
            X = X.values
        predictions = np.array([tree.predict(X) for tree in self.trees])
        tree_preds = np.swapaxes(predictions, 0, 1)

        if self.treetype=="classification":
            predictions = np.array([self._most_common_label(pred) for pred in tree_preds])
        elif self.treetype=="regression":
            predictions = np.mean(tree_preds, axis=1)

        return predictions