import numpy as np
from tensorflow import keras 
import pickle

   
class OddsCalculator():
    
    def __init__(self,model_path,scaler_path):
        self.model = self.load_network(model_path)
        self.scaler = self.load_scaler(scaler_path)
        print(self.scaler,self.model)
   
    #######     
    def load_network(self,path):
        return keras.models.load_model(path)
    
    def load_scaler(self,path):
        with open(path,"rb") as f:
            return pickle.load(f)
    #######
    
    def odds_calculate(self,percentage):
        first = round((1/percentage)-1,3)
        last = 1 
        return str(first)+"/"+str(last)

    def calculate(self,stake,odds):   
        return stake + stake*(float(odds[:3]))
    
    def preprocess(self,xp,gold,bet_minute):
        xp, gold = xp[bet_minute], gold[bet_minute]
        dt = np.array([bet_minute, xp, gold]).reshape(1,3)
        return self.scaler.transform(dt)
    
    def network_predict(self,xp,gold,bet_minute,team,pred_result):
        pred = self.model.predict(self.preprocess(xp,gold,bet_minute))[0][0]
        if (team == 1) & (pred_result=="win"):
            result = pred
            return result
        elif (team==1) & (pred_result=="lose"):
            result = (1-pred)
            return result
        elif (team==-1) & (pred_result=="lose"):
            result= pred
            return result
        else:
            result = (1-pred)
            return result
                    
    def payout(self,xp,gold,bet_minute,bet_value,team,pred_result):
        bet_minute = int(bet_minute)
        pred = self.network_predict(xp,gold,bet_minute,team,pred_result) 
        odds = self.odds_calculate(pred)
        payout = self.calculate(bet_value,odds)
        return odds, payout
    
##########

if __name__=="__main__":
    
    from dota_client import DotaClient
    
    dc = DotaClient("3155b9f3-895a-4e0a-853b-8a04f1166cb9")
    
    scaler_path = "C:\\Users\\u2094706\\Desktop\\python-dota-main\\DotaBot_v2\\Odds Module\\scaler.pkl"
    model_path = "C:\\Users\\u2094706\\Desktop\\python-dota-main\\DotaBot_v2\\Odds Module\\Odds_NN"   


    data = dc.get_match_by_id(6454415871)
    xp, gold, start_time = data['radiant_xp_adv'], data['radiant_gold_adv'], data['start_time']
    
    bet_time = int(start_time)+(8*60)
    pred_result='win'
    
    oc = OddsCalculator(model_path,scaler_path)
    
    odds,val = oc.payout(xp,gold,start_time,bet_time,100,1,pred_result)
    print(odds,val)
    
    
    
