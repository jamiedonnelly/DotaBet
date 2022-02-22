from sqlite3 import InterfaceError
import numpy as np 
import mysql.connector
from functools import wraps
import time
import pandas as pd

"""
    Python class for handling interaction with a mysql database acting as a ledger for a discord gambling bot.
"""

class Balances():

    def __init__(self, host, user, database, password):
        self.host, self.user, self.database, self.password = host, user, database, password 
        self.connect()
        
    def connect(self):
        self.conn = mysql.connector.connect(host=self.host, user=self.user, database=self.database, password=self.password)
        self.cursor = self.conn.cursor()
        print("Established connection...")
    
    #### Function decorators     
    def _commit(func):
        @wraps(func)
        def wrap(self, *args, **kwargs):
            result = func(self, *args, **kwargs)
            self.conn.commit()
            return result
        return wrap
    
    def _reconnect(func):
        @wraps(func)
        def rec(self,*args,**kwargs):
            try:
                result = func(self,*args,**kwargs)
                return result
            except (mysql.connector.Error, mysql.connector.Warning) as e:
                self.connect()
                result = func(self,*args,**kwargs)
                return result
        return rec     
    ####

    @_commit
    @_reconnect
    def new_user(self,user_id):
        if not self.check_user_exists(user_id):
            cmd = "INSERT INTO balances (timestamp, user_id, balance) VALUES ({},{},5000);".format(time.time(),user_id)
            self.cursor.execute(cmd)
        
    @_commit
    @_reconnect
    def reset_balance(self,user_id):
        cmd = "INSERT INTO balances (timestamp,user_id,balance) VALUES ({},{},5000);".format(time.time(),user_id)
        self.cursor.execute(cmd)
        return        
        
    @_commit
    @_reconnect
    def remove_user(self,user_id):
        if self.check_user_exists(user_id):
            cmd = "DELETE FROM balances where user_id={};".format(user_id)
            self.cursor.execute(cmd)
            
    def rows_to_array(self,data):
        dt = []
        for i in data:
            dt.append([j for j in i])
        return np.array(dt)
    
    @_reconnect
    def get_entries(self,user_id,limit=None):
        cmd = "SELECT * FROM balances WHERE user_id={} ORDER BY timestamp DESC;".format(user_id)
        self.cursor.execute(cmd)
        result = self.rows_to_array(self.cursor.fetchall())
        if limit: 
            return result[:limit]
        else:
            return result

    @_reconnect
    def get_balance(self,user_id):
        if self.check_user_exists(user_id):
            cmd = "SELECT balance FROM balances WHERE user_id={} ORDER BY timestamp DESC limit 1;".format(user_id)
            self.cursor.execute(cmd)              
            return int(self.cursor.fetchall()[0][0])

    @_reconnect
    def check_user_exists(self,user_id):
        cmd = "SELECT COUNT(*) FROM balances where user_id={};".format(user_id)
        self.cursor.execute(cmd)
        if self.cursor.fetchall()[0][0]==0:
            return False 
        else:
            return True
        
    @_commit
    @_reconnect
    def new_entry(self,user_id,money):
        if self.check_user_exists(user_id):
            balance = self.get_balance(user_id)
            balance += money
            cmd="INSERT INTO balances (timestamp, user_id, balance) VALUES ({},{},{});".format(time.time(),user_id,balance)
            self.cursor.execute(cmd)
        else:
            self.new_user(user_id)
            self.new_entry(user_id,money)
            
    @_reconnect
    def select_all_users(self):
        cmd = "SELECT DISTINCT user_id FROM balances;"
        self.cursor.execute(cmd)
        return 
    
    def rows_to_df(self,data):
        N = len(data)
        df = pd.DataFrame(columns=['balance'])
        return
        
        

class UserInfo():
    
    def __init__(self, host, user, database, password):
        self.host, self.user, self.database, self.password = host, user, database, password 
        self.connect()
        
    def connect(self):
        self.conn = mysql.connector.connect(host=self.host, user=self.user, database=self.database, password=self.password)
        self.cursor = self.conn.cursor()
        print("Established connection...")
    
    #### Function decorators     
    def _commit(func):
        @wraps(func)
        def wrap(self, *args, **kwargs):
            result = func(self, *args, **kwargs)
            self.conn.commit()
            return result
        return wrap
    
    def _reconnect(func):
        @wraps(func)
        def rec(self,*args,**kwargs):
            try:
                result = func(self,*args,**kwargs)
                return result
            except (mysql.connector.Error, mysql.connector.Warning) as e:
                self.connect()
                result = func(self,*args,**kwargs)
                return result
        return rec     
    ####
    
    @_commit
    @_reconnect
    def config_steam(self,user_id,steam_id):
        if not self.check_user_exists(user_id):
            cmd = "INSERT INTO userinfo (user_id, steam_id) VALUES ({}, {})".format(user_id, steam_id)
            self.cursor.execute(cmd)
            return
        else:
            self.drop_user(user_id)
            self.config_steam(user_id,steam_id) 
                   
    @_commit
    @_reconnect
    def drop_user(self,user_id):
        if self.check_user_exists(user_id):
            cmd = "DELETE FROM userinfo WHERE user_id={};".format(user_id)
            self.cursor.execute(cmd)
            return 
            
    @_reconnect
    def check_user_exists(self,user_id):
        cmd = "SELECT COUNT(*) FROM userinfo where user_id={};".format(user_id)
        self.cursor.execute(cmd)
        if self.cursor.fetchall()[0][0]==0:
            return False 
        else:
            return True
        
    @_reconnect
    def get_steam_id(self,user_id):
        cmd = "SELECT steam_id FROM userinfo where user_id={};".format(user_id)
        self.cursor.execute(cmd)
        result = int(self.cursor.fetchall()[0][0])
        return result 
        
    @_reconnect
    def get_all_configured_users(self):
        cmd = "SELECT DISTINCT user_id FROM userinfo;"
        self.cursor.execute(cmd)
        result = [i[0] for i in self.cursor.fetchall()]
        return result 

if __name__=="__main__":
    
    host = ''
    user = ''
    database = ''
    password=''
    
    bal = Balances(host,user,database,password)
    

        
    

    

        
