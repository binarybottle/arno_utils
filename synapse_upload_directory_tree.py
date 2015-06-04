#!/usr/bin/env python                                                                                                       
"""                                                                                                                         
Recursively upload a directory structure to a Synapse project (synapse.org).                                                
                                                                                                                            
Examples::                                                                                                                  
                                                                                                                            
    synapse_upload_directory_tree <PROJECT ID> -user <EMAIL> --pass <PASS> --top <TOP DIRECTORY>
    synapse_upload_directory_tree syn3207152 --user arno.klein@sagebase.org --pass XXXXXX --top brains

    synapse_upload_directory_tree syn3207152 --user arno.klein@sagebase.org --pass XXXXXX --top brains --file-db synapse_file_upload_directory_tree.sqlite

After Larsson's 2014/10/24 GitHub Gist:                                                                                     
https://gist.github.com/larssono/db35917cf58440fe0b19

The SQLite 3 database file specified in the --file-db acts as a local cache of
files that have already been uploaded. To bypass use of the cache, specify a
different filename or delete the database file. The file-db defaults to:
synapse_file_upload_directory_tree.sqlite

Copyright 2015, Sage Bionetworks (http://sagebase.org), Apache v2.0 License
"""
import os
import sqlite3
import synapseclient
from synapseclient import File, Folder
import argparse

#-----------------------------------------------------------------------------                                              
# File names should not contain these strings:                                                                              
#-----------------------------------------------------------------------------                                              
ignore_strings = ['~','!','@','#','$','%','^','&','*','(',')','+','`','=']

#-----------------------------------------------------------------------------                                              
# File types inferred by their appends:                                                                                     
#-----------------------------------------------------------------------------                                              
types = ['.nii','.nii.gz','.vtk','.mgz']
type_names = ['nifti','nifti','vtk','mgz']

#-----------------------------------------------------------------------------                                              
# Command-line arguments:                                                                                                   
#-----------------------------------------------------------------------------                                              
parser = argparse.ArgumentParser(description="""                                                                            
                    Recursively upload a directory structure to synapse.org.""",
                     formatter_class = lambda prog:
                     argparse.HelpFormatter(prog, max_help_position=40))
parser.add_argument("project_id",
                    help='Synapse Project ID, such as "syn32071528"')
parser.add_argument("-u", "--user", help="Synapse User Name", default=None)
parser.add_argument("-p", "--password", help="Synapse Password", default=None)
parser.add_argument("--file-db", help="SQLite database of tracking last modified dates of files to upload", default="synapse_file_upload_directory_tree.sqlite")
parser.add_argument("--top",
                    help='Topmost directory',
                    default='.', type=str, metavar='STR')
args = parser.parse_args()

project_id = args.project_id
user = args.user
password = args.password
start_path = args.top
syn=synapseclient.login(user, password) #(silent=True)

conn = sqlite3.connect(args.file_db)
try:

    #-----------------------------------------------------------------------------                                              
    # get cached file and directory info from SQLite:                                                          
    #-----------------------------------------------------------------------------                                              
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS files (path TEXT, mtime REAL);')
    c.execute('CREATE TABLE IF NOT EXISTS folders (path TEXT, synapse_id TEXT);')

    print('Reading file table...')
    previous_uploads = {}
    result = c.execute('SELECT path, mtime from files;')
    for row in result:
        previous_uploads[row[0]] = row[1]

    print('Reading folder table...')
    parents = {start_path: project_id}
    result = c.execute('SELECT path, synapse_id from folders;')
    for row in result:
        parents[row[0]] = row[1]

    #-----------------------------------------------------------------------------                                              
    # Start walking through the source directory tree from start_path:                                                          
    #-----------------------------------------------------------------------------                                              
    for dirpath, dirnames, filenames in os.walk(start_path):

        #-------------------------------------------------------------------------                                              
        # Make each subdirectory (and store its path):                                                                          
        #-------------------------------------------------------------------------                                              
        for dirname in dirnames:
            path = os.path.join(dirpath, dirname)

            if path not in parents:
                print('Creating {0}...'.format(dirname))
                f = syn.store(Folder(dirname, parent=parents[dirpath]))
                parents[path] = f.id

                c = conn.cursor()
                c.execute('INSERT OR REPLACE INTO folders (path, synapse_id) VALUES ("%s", "%s")' % (path, f.id))
                conn.commit()


        #-------------------------------------------------------------------------                                              
        # Loop through the file names:                                                                                          
        #-------------------------------------------------------------------------                                              
        for filename in filenames:

            #---------------------------------------------------------------------                                              
            # Make sure each file name does not contain any ignore_strings:                                                     
            #---------------------------------------------------------------------                                              
            okay = True
            for str0 in ignore_strings:
                if str0 in filename:
                    okay = False
            if okay:

                #-----------------------------------------------------------------                                              
                # Upload the file to the correct path:                                                                          
                #-----------------------------------------------------------------                                              
                path = os.path.join(dirpath, filename)
                stat = os.stat(path)
                if stat.st_size > 0:

                    mtime = stat.st_mtime
                    previous_mtime = previous_uploads.get(path, None)
                    if mtime > previous_mtime:

                        print('Uploading {0}...'.format(path))
                        f = File(path, parent=parents[dirpath], name=filename)

                        #-------------------------------------------------------------                                              
                        # Annotate the file on Synapse:                                                                             
                        #-------------------------------------------------------------                                              
                        for istr2, str2 in enumerate(types):
                            if filename.endswith(str2):
                                f.fileType = type_names[istr2]

                        # Optionally add "syn.store(f, used='http://..)"                                                            
                        # to specify the source location                                                                            
                        syn.store(f)

                        c = conn.cursor()
                        c.execute('INSERT OR REPLACE INTO files (path, mtime) VALUES ("%s", "%s")' % (path, mtime))
                        conn.commit()

finally:
    conn.close()


