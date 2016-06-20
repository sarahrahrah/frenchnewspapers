#!/usr/bin/env python3

from nltk import word_tokenize, FreqDist
from nltk.corpus import stopwords, names
import codecs
import os
import drive
import re
import csv
import operator
import dateutil.parser


CORPUS = 'clean_ocr'


def generate_stopwords():
    """generates stopwords for use in tokenizing"""
    nltk_stopwords = stopwords.words('french')
    # stopwords from http://www.ranks.nl/stopwords/french
    ranks_stopwords = []
    with codecs.open('french_stopwords.txt', 'r', 'utf8') as f:
        ranks_stopwords = [x.strip('\n') for x in f]
    # put custom stopword list here. Could also
    # read in as a csv file if that's easier.
    extra_stopwords = []
    punctuation = ['»', '«', ',', '-', '.', '!',
                   "\"", '\'' ':', ';', '?', '...']
    return set(nltk_stopwords + ranks_stopwords +
               punctuation + extra_stopwords)


def names_list():
    """puts together a list to query the corpus by"""
    nltk_names = names.words()
    # put custom name list here.
    extra_names = ['Alexandre', 'Steinheil']
    return [w.lower() for w in nltk_names] + [w.lower() for w in extra_names]


LIST_OF_NAMES = names_list()


def all_file_names(dirname=CORPUS):
    """Reads in the files"""
    for (root, _, files) in os.walk(dirname):
        for fn in files:
            yield os.path.join(root, fn)


def strip_off_file_path(filename):
    """Takes off extraneous information from the file
     path and returns the filename alone"""
    filename = re.sub(r'^.*/|_clean.txt', '', filename)
    return filename.lower()


def read_all_texts(filenames):
    """Given a list of filenames, read each of them"""
    for f in filenames:
        yield (strip_off_file_path(f), read_text(f))


def get_articles_metadata(list_of_articles, debug=False):
    """takes articles in form of [filename, [tokens]],
    goes out to google drive and gives it the necessary
    date and time information."""
    metadata = drive.get_article_metadata()
    new_list_of_articles = []
    for article in list_of_articles:
        for row in metadata:
            if row['filename'] == article[0]:
                new_list_of_articles.append({'file_name': article[0],
                                             'journal': row['newspaper name'],
                                             'date': row['date'],
                                             'tokens': tokenize_text(article[1])
                                             })
            elif debug:
                print("********ERROR: FILENAME AND DATE MISMATCH ********")
                print(row['filename'] + '   ≠   ' + article[0])
                print("*************")
            else:
                pass
    return new_list_of_articles


def read_text(filename):
    """given a filename read in the text."""
    with codecs.open(filename, 'r', 'utf8') as f:
        return f.read()


def tokenize_text(file):
    """Tokenizes the text as is. Strips out page breaks and
    derniere sections but leaves them as part of the larger text."""
    return [w.lower() for w in word_tokenize(file)]


def remove_stopwords(tokens):
    """takes a list of tokens and strips out the stopwords"""
    stopword_list = generate_stopwords()
    return [w for w in tokens if w.lower() not in stopword_list]


def calc_article_length(tokens):
    """given an article's tokens calculates its length"""
    return len(tokens)


def count_punctuation(text):
    """Gives a count of the given punctuation marks for each text"""
    fd = FreqDist(text)
    punctuation_marks = ['»', '«', ',', '-', '.', '!',
                         "\"", ':', ';', '?', '...', '\'']
    for mark in punctuation_marks:
        count = str(fd[mark])
        yield "%(mark)s, %(count)s" % locals()


def single_token_count(text, token):
    """takes a token set and returns the counts for a single mark."""
    fd = FreqDist(text)
    return fd[token]


def most_common(text):
    """takes a series of tokens and returns most common 50 words."""
    fd = FreqDist(remove_stopwords(text))
    return fd.most_common(50)


def find_names(text, list_of_names=LIST_OF_NAMES):
    """creates a frequency distribution of the
    most common names in the texts"""
    name_tokens = [w for w in text if w in list_of_names]
    fd = FreqDist(name_tokens)
    return fd.most_common(50)


def read_out(articles):
    """given a series of articles, print out stats for them
    articles are given as a list of tuple pairs (filename, list of tokens)"""
    output = open('results.txt', 'w')
    for article in articles:
        output.write("===================\n")
        output.write(article['file_name'] + '\n')
        output.write("Number of tokens: " +
                     str(calc_article_length(article['tokens'])) + '\n')
        output.write("Most common tokens: " +
                     str(most_common(article['tokens'])) + '\n')
        output.write("Punctuation Counts: " +
                     str([mark for mark
                          in count_punctuation(article['tokens'])]) + '\n')
        output.write("Names: " + str(find_names(article['tokens'])) + '\n')


def prepare_all_texts(corpus=CORPUS):
    """Takes all files from filenames to dict. runs everything in between"""
    # reads in all filenames from the corpus directory.
    file_names = list(all_file_names(corpus))
    # reads in data of texts
    texts = list(read_all_texts(file_names))
    # reads in article metadata for texts
    texts_with_metadata = get_articles_metadata(texts)
    return texts_with_metadata


def parse_dates(date):
    date = dateutil.parser.parse(date)
    key = ('%s-%s-%s' % (date.year, date.month, date.day))
    return key


def sort_by_date(articles, token):
    """Takes the list of articles and the parameter to sort by.
    returns all the data needed for the CSV
    returns a hash with key values of {(year, month, day):
    (target token counts for
    this month, total tokens)}"""
    index = {}
    for article in articles:
        key = parse_dates(article['date'])
        date_values = index.get(key)
        if date_values is None:
            total_doc_tokens = len(article['tokens'])
            date_values = single_token_count(article['tokens'], token)
            index[key] = (date_values, total_doc_tokens)
        else:
            index[key] = (index[key][0] + single_token_count(article['tokens'], token), index[key][1] + len(article['tokens']))
        index['year-month-day'] = token
    return index

# TODO: CSV write out for visualizing
# TODO: stemming


def dict_to_list(a_dict):
    """takes the result dict and prepares it for writing to csv"""
    rows = []

    for (date_key, values) in a_dict.items():
        try:
            tf_idf = values[0] / values[1]
            rows.append([date_key, tf_idf])
        except:
            # for the csv header, put it at the beginning of the list
            rows.insert(0, [date_key, values])
    # sorts things by date
    rows.sort(key=operator.itemgetter(0))
    # takes the last row and makes it first, since it gets shuffled to the back
    rows.insert(0, rows.pop())
    return rows


def csv_dump(results_dict):
    """writes some information to a CSV for graphing in excel."""
    results_list = dict_to_list(results_dict)

    with open('results.csv', 'w') as csv_file:
        csvwriter = csv.writer(csv_file, delimiter=',')
        for row in results_list:
            csvwriter.writerow(row)



def main():
    """Main function to be called when the script is called"""
    text_data = prepare_all_texts()
    index = sort_by_date(text_data, 'crime')
    csv_dump(index)
    # read_out(text_data)

if __name__ == '__main__':
    main()
