import os
import sqlite3
import subprocess

def get_user_data(user_id):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    query = "SELECT * FROM users WHERE id = " + str(user_id)
    cursor.execute(query)
    return cursor.fetchall()

def execute_command(user_input):
    os.system(f"ping -c 4 {user_input}")

def load_module(module_name):
    exec(f"import {module_name}; {module_name}.run()")
