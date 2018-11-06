import sqlite3
import nltk
from nltk.tokenize import word_tokenize
from tqdm import tqdm
import random
import re
from string import punctuation
from tts import speak



VERSION = "3.0"
NAME = "Alex_v{}".format(VERSION)

PUNCT = list(punctuation)

print("Connecting to {} database...".format(NAME))
con = sqlite3.connect('./{}.db'.format(NAME))
c = con.cursor()
print("Connected!!!")

# Create all the tables needed
def create_table():
    tables = [
    "CREATE TABLE associations(parent TEXT NOT NULL, reply TEXT NOT NULL, word_id INT NOT NULL, word_weight REAL NOT NULL, occurence INT NOT NULL DEFAULT 1)",
    "CREATE TABLE words(word TEXT NOT NULL)"
    ]

    try:
        for i in tables:
            c.execute(i)
    except:
        pass

# Get id of a specific word / Create a new row if not exist
def get_id(word):
    c.execute("SELECT rowid from words WHERE word = ?", (word,))
    rowid = c.fetchone()

    if rowid:
        return rowid[0]
    else:
        c.execute("INSERT INTO words(word) VALUES (?)", (word,))
        con.commit()
        return c.lastrowid

# Get weight of words base on the word list (ranging from 0~1)
def get_weight(word_list, word):
    total_words = len(word_list)

    occur = 0
    for w in word_list:
        if word == w:
            occur += 1

    weight = float(occur)/float(total_words)
    return weight

def clean_text(text):
    '''Clean text by removing unnecessary characters and altering the format of words.'''

    text = text.lower()
    
    text = re.sub(r"i'm", "i am", text)
    text = re.sub(r"he's", "he is", text)
    text = re.sub(r"she's", "she is", text)
    text = re.sub(r"it's", "it is", text)
    text = re.sub(r"that's", "that is", text)
    text = re.sub(r"what's", "that is", text)
    text = re.sub(r"where's", "where is", text)
    text = re.sub(r"how's", "how is", text)
    text = re.sub(r"\'ll", " will", text)
    text = re.sub(r"\'ve", " have", text)
    text = re.sub(r"\'re", " are", text)
    text = re.sub(r"\'d", " would", text)
    text = re.sub(r"\'re", " are", text)
    text = re.sub(r"won't", "will not", text)
    text = re.sub(r"can't", "cannot", text)
    text = re.sub(r"n't", " not", text)
    text = re.sub(r"n'", "ng", text)
    text = re.sub(r"'bout", "about", text)
    text = re.sub(r"'til", "until", text)
    text = re.sub(r"[-()\"#/@;:<>{}`+=~|.!?,]", "", text)

    return text


class train_fn(object):
    def __init__(self, path):
        self.path = path

    # Append and update data into the database
    def train(self, parent, reply):
        # Tokenize sentence into words
        raw_parent_words = word_tokenize(clean_text(parent))

        # Remove punctuations
        parent_words = [p for p in raw_parent_words if p not in PUNCT]

        # Get ids for each word
        parent_id = []

        for word in parent_words:
            word_id = get_id(word)
            parent_id.append(word_id)

        # Get the weight for each word in the specific sentence
        parent_weight = []

        for word in parent_words:
            word_weight = get_weight(parent_words, word)
            parent_weight.append(word_weight)

        # Search for similar data to increase occurence or insert new data into the database
        c.execute("SELECT occurence, rowid FROM associations WHERE parent = ? AND reply = ?", (parent, reply,))
        row_info = c.fetchone()

        if row_info:
            new_occur = int(row_info[0]) + 1

            c.execute("UPDATE associations SET (occurence) = (?) WHERE rowid = ?",
                (str(new_occur), str(row_info[1]),))

        else:
            c.execute("INSERT INTO associations(parent, reply, word_id, word_weight) VALUES (?, ?, ?, ?)",
                (parent, reply, str(parent_id), str(parent_weight),))

        con.commit()

    def train_file(self, filename):
        file = f'{self.path}/{filename}'
        data = open(file, 'r').read().split('\n')

        # remove all blank elements
        data = [d for d in data if ((d is not None) and (d is not '') and (d is not ' '))]

        start_index = data.index('conversations:') + 1

        parent = [''.join(list(p)[4:]) for p in data[start_index:] if ((data.index(p) - start_index) % 2) == 0]
        reply = [''.join(list(p)[4:]) for p in data[start_index:] if ((data.index(p) - start_index) % 2) == 1]

        if len(parent) == len(reply):
            for i in tqdm(range(len(parent))):
                self.train(parent[i], reply[i])

        else:
            print('[Error]:\nLine 142: length of `parent` is not equal to lenght of `reply`')



# Generate a response base on the database
def get_response(sentence):
    try:
        raw_sentence = sentence.lower()
        words = word_tokenize(raw_sentence)

        filtered_words = [f for f in words if f not in PUNCT]
        word_id = []

        for w in filtered_words:
            w_id = get_id(w)
            word_id.append(w_id)


        c.execute("SELECT * FROM associations")
        raw_data = c.fetchall()
        # FORMAT of raw_data
        # [parent, reply, word_id, word_weight, occurence]

        selected_rows = []
        for r in raw_data:
            raw_word_id = eval(r[2])

            for i in word_id:
                if i in raw_word_id:
                    selected_rows.append(r)
                    break

        selected_row_weight = []
        for s in selected_rows:
            weight = 0
            used_word_id = []
            raw_word_id = eval(s[2])
            raw_word_weight = eval(s[3])

            for i in range(len(raw_word_id)):
                if raw_word_id[i] in word_id and raw_word_id[i] not in used_word_id:
                    weight += raw_word_weight[i]
                    used_word_id.append(raw_word_id[i])

            selected_row_weight.append(weight)

        favored_weight = 1.0
        higest_weight = min(selected_row_weight, key=lambda x:abs(x-favored_weight))
        best_rows = []

        for i in range(len(selected_row_weight)):
            if selected_row_weight[i] == higest_weight:
                best_rows.append(selected_rows[i][1])

        best_rows = [best_rows, higest_weight*100]

        return best_rows

    # Get a response that has the least occurence
    except:
        least_occur = []
        all_occur = 0

        for r in raw_data:
            all_occur += r[4]

        average_occur = int(all_occur/len(raw_data))

        for r in raw_data:
            if r[4] <= average_occur:
                least_occur.append(r[1])

        least_occur = [least_occur, 0.0]

        return least_occur


# Create a filtered reply
def get_final_reply(sentence):
    sentence = sentence.lower()
    best_replies = get_response(sentence)

    final_reply = random.choice(best_replies[0])
    return [final_reply, best_replies[1]]

# Create a quick and simple user_interaction to the user.
def user_interaction():
    try:
        bot_input = ""
        user_input = ""
        while True:
            if user_input == "":
                user_input = input("[USER]: ")
                speak(user_input)
            else:
                bot_input = get_final_reply(user_input)
                print("[{}]:".format(NAME), bot_input[0], "Confidence level:", bot_input[1])
                speak(bot_input[0])
                user_input = input("[USER]: ")
                speak(user_input)

    except Exception as e:
        print("\n[ERRORS]:\n")
        print(str(e))
        print("Closing the conversation...")
        con.commit()


# Essential for every operations, only uncomment if you know what you are doing
create_table()

# Uncomment to run user interaction in Command Prompt (CMD)
user_interaction()

# Uncomment to train
'''
files = [
'ai.yml',
'botprofile.yml',
'conversations.yml',
'emotion.yml',
'food.yml',
'greetings.yml',
'history.yml',
'humor.yml',
'literature.yml',
'money.yml',
'movies.yml',
'politics.yml',
'psychology.yml',
'science.yml',
'sports.yml',
'trivia.yml'
]

trn_f = train_fn('./data')

for f in files:
    print(f'\nTraining on: {f}')
    trn_f.train_file(f)
'''

