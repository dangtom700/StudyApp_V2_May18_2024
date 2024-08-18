"""
WORDS FOUND IN RESPECT TO TITLES AND CONTENTS

Purpose:
- To count the word frequency in respect to titles and their contents
- To compute the impact of certain words in specific contents

Tasks:
- Set up a table with one column is the foreign key to the word column in the 
    word_frequencies table, and another column is the frequency of the word and
    other columns are the list of titles

- Set another table to compute TF-IDF values for each word in each title. The
    first column is the foreign key to the word column in the word_frequencies,
    and other columns are the TF-IDF values for each word in each title

- Default parameter for the words column is most covered in text chunk analysis
    to faster compute the impact of each words to avoid zero containment matrix
    in most cases

- Optimize the query to improve the performance of the program
- Parallelize the process to reduce the time cost of the program
"""