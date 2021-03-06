import inflect as inflect
import numpy as np
import pandas as pd
from flask import Flask, render_template, request

from scipy.sparse.linalg import svds
import re, string, unicodedata
import nltk
import contractions
from bs4 import BeautifulSoup

from nltk.corpus import stopwords
from nltk.stem.lancaster import LancasterStemmer
from nltk.stem import WordNetLemmatizer

import pickle


# load the nlp model and tfidf vectorizer from disk
filename = 'models/recom_model.pkl'
clf = pickle.load(open(filename, 'rb'))
vectorizer = pickle.load(open('models/vect.pkl','rb'))

def preprocess(product_ratings):
    product_ratings.drop(['reviews_doRecommend', 'reviews_didPurchase', 'categories', 'reviews_date', 'manufacturer', 'categories',
         'brand', 'reviews_text', 'reviews_title', 'reviews_userCity', 'reviews_userProvince', 'user_sentiment', 'id'], axis=1, inplace=True)

    prod_ratings = product_ratings.rename(columns={'name': 'product_title', 'reviews_username': 'reviews_username'})
    prod_ratings=prod_ratings.dropna()

    counts1 = prod_ratings['reviews_username'].value_counts()
    counts = prod_ratings['product_title'].value_counts()

    df = prod_ratings[prod_ratings['reviews_username'].isin(counts1[counts1 >= 1].index)]
    df = df[df['product_title'].isin(counts[counts >= 10].index)]

    prod_ratings.head()
    df1 = df.drop_duplicates(subset=['reviews_username','product_title',],keep='first')
    df3 = df1.sort_values(by='reviews_rating')
    df3 = df3.reset_index(drop=True)
    return df3
    


def rcmd(username):
    username = username.lower()
    data_in = pd.read_csv('datasets/sample30.csv')

    data_in['reviews_username'] = data_in['reviews_username'].str.lower()
    if username not in data_in['reviews_username'].unique():
        return('Sorry! User not Found!!! ')

    data = preprocess(data_in)


    count = data.groupby("product_title", as_index=False).mean()
    items_df = count[['product_title']]

    count_users = data.groupby("reviews_username", as_index=False).count()
    users_df = count_users[['reviews_username']]

    df_clean_matrix = data.pivot(index='product_title', columns='reviews_username', values='reviews_rating').fillna(0)

    df_clean_matrix = df_clean_matrix.T
    R = (df_clean_matrix).to_numpy()
    user_ratings_mean = np.mean(R, axis=1)
    R_demeaned = R - user_ratings_mean.reshape(-1, 1)
    U, sigma, Vt = svds(R_demeaned)
    sigma = np.diag(sigma)

    all_user_predicted_ratings = np.dot(np.dot(U, sigma), Vt) + user_ratings_mean.reshape(-1, 1)
    preds_df = pd.DataFrame(all_user_predicted_ratings, columns=df_clean_matrix.columns)
    preds_df['reviews_username'] = users_df
    preds_df.set_index('reviews_username', inplace=True)
    
    recommend_df = recommend_it(preds_df, items_df, data, 15, username)
    
    l = list(recommend_df['product_title'])

    for i in l:
        Rating = sentiment(i)
        
        ln = len(Rating)
        Avg_rat = Rating.sum()/ln
        
        recommend_df.loc[recommend_df['product_title'] == i,'Avg_rat'] = round(Avg_rat*100,2)

    top5 = recommend_df.sort_values('Avg_rat', ascending=False).head(5)

    top5.rename(columns={'product_title':'Recommended Products','Avg_rat':'Postive Sentiments %'},inplace=True)
    
    return top5

def sentiment(product):
    data_in = pd.read_csv('datasets/sample30.csv')
    data2 = data_in[data_in['name'] == product]
    data2['reviewstext'] = data2[['reviews_title', 'reviews_text']].apply(
        lambda x: " ".join(str(y) for y in x if str(y) != 'nan'), axis=1)
    data2['clean_reviewstext'] = data2['reviewstext'].map(lambda text: normalize_and_lemmaize(text))

    X_test = data2['clean_reviewstext']

    X_test.head()
    

    count_vect_test = vectorizer.transform(X_test)
    count_vect_test = count_vect_test.toarray()
    Pred_rating =clf.predict(count_vect_test)

    return Pred_rating

def strip_html(text):
    soup = BeautifulSoup(text, "html.parser")
    return soup.get_text()

def remove_between_square_brackets(text):
    return re.sub('\[[^]]*\]', '', text)

def denoise_text(text):
    text = strip_html(text)
    text = remove_between_square_brackets(text)
    return text


def remove_special_characters(text, remove_digits=True):
    pattern = r'[^a-zA-z0-9\s]' if not remove_digits else r'[^a-zA-z\s]'
    text = re.sub(pattern, '', text)
    return text


def remove_non_ascii(words):
    """Remove non-ASCII characters from list of tokenized words"""
    new_words = []
    for word in words:
        new_word = unicodedata.normalize('NFKD', word).encode('ascii', 'ignore').decode('utf-8', 'ignore')
        new_words.append(new_word)
    return new_words

def to_lowercase(words):
    """Convert all characters to lowercase from list of tokenized words"""
    new_words = []
    for word in words:
        new_word = word.lower()
        new_words.append(new_word)
    return new_words


def remove_punctuation_and_splchars(words):
    """Remove punctuation from list of tokenized words"""
    new_words = []
    for word in words:
        new_word = re.sub(r'[^\w\s]', '', word)
        if new_word != '':
            new_word = remove_special_characters(new_word, True)
            new_words.append(new_word)
    return new_words

def replace_numbers(words):
    """Replace all interger occurrences in list of tokenized words with textual representation"""
    p = inflect.engine()
    new_words = []
    for word in words:
        if word.isdigit():
            new_word = p.number_to_words(word)
            new_words.append(new_word)
        else:
            new_words.append(word)
    return new_words

stopword_list= stopwords.words('english')
stopword_list.remove('no')
stopword_list.remove('not')


def remove_stopwords(words):
    """Remove stop words from list of tokenized words"""
    new_words = []
    for word in words:
        if word not in stopword_list:
            new_words.append(word)
    return new_words

def stem_words(words):
    """Stem words in list of tokenized words"""
    stemmer = LancasterStemmer()
    stems = []
    for word in words:
        stem = stemmer.stem(word)
        stems.append(stem)
    return stems

def lemmatize_verbs(words):
    """Lemmatize verbs in list of tokenized words"""
    lemmatizer = WordNetLemmatizer()
    lemmas = []
    for word in words:
        lemma = lemmatizer.lemmatize(word, pos='v')
        lemmas.append(lemma)
    return lemmas

def normalize(words):
    words = remove_non_ascii(words)
    words = to_lowercase(words)
    words = remove_punctuation_and_splchars(words)
    words = remove_stopwords(words)
    return words

def lemmatize(words):
    lemmas = lemmatize_verbs(words)
    return lemmas

def normalize_and_lemmaize(input):
    sample = denoise_text(input)
      

    sample = contractions.fix(sample)
    sample = remove_special_characters(sample)
    words = nltk.word_tokenize(sample)
    words = normalize(words)
    lemmas = lemmatize(words)
    return ' '.join(lemmas)



def recommend_it(predictions_df, itm_df, original_ratings_df, num_recommendations=10, ruserId='joshua'):
    
    sorted_user_predictions = predictions_df.loc[ruserId].sort_values(ascending=False)

    
    user_data = original_ratings_df[original_ratings_df.reviews_username == ruserId]
    user_full = (user_data.merge(itm_df, how='left', left_on='product_title', right_on='product_title').
                 sort_values(['reviews_rating'], ascending=False)
                 )

   
    recommendations = (itm_df[~itm_df['product_title'].isin(user_full['product_title'])].
                           merge(pd.DataFrame(sorted_user_predictions).reset_index(), how='left',
                                 left_on='product_title',
                                 right_on='product_title').
                           rename(columns={ruserId: 'Predictions'}).
                           sort_values('Predictions', ascending=False).
                           iloc[:num_recommendations, :-1]
                           )
    topk = recommendations.merge(original_ratings_df, right_on='product_title',
                                 left_on='product_title').drop_duplicates(['product_title'])[['product_title']]

    return topk