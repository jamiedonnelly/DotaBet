import numpy as np
from tensorflow import keras 
import pickle

   
class OddsCalculator():
    
    def __init__(self,model_path,scaler_path):
        self.model = self.load_network(model_path)
        self.scaler = self.load_scaler(scaler_path)
   
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
        return round(float(stake*(float(odds[:3]))),2)
    
    def preprocess(self,data,bet_time):
        bet_minute = (bet_time-(data['start_time']+150))//60
        dt = np.array([bet_minute, data['radiant_xp_adv'][bet_minute], data['radiant_gold_adv'][bet_minute]])
        return self.scaler.transform(dt.reshape(1,3))
    
    def network_predict(self,data,team,bet_time,pred_result):
        pred = self.model.predict(self.preprocess(data,bet_time))[0][0]
        if (team == 1) & (pred_result=="win"):
            return pred 
        elif (team==1) & (pred_result=="lose"):
            return (1-pred)
        elif (team==-1) & (pred_result=="lose"):
            return pred 
        else:
            return (1-pred)
                    
    def payout(self,data,bet_time,bet_value,team,pred_result):
        pred = self.network_predict(data,team,bet_time,pred_result) 
        odds = self.odds_calculate(pred)
        payout = self.calculate(bet_value,odds)
        return odds, payout
    
##########

if __name__=="__main__":
    
    from dota_client import DotaClient
    
    dc = DotaClient({api_key})
    
    scaler_path = ".../scaler.pkl"
    model_path = ".../Odds_NN"    


    data = dc.get_match_by_id(6428477137)
    
    bet_time = 1644685464+(8*60)
    pred_result='win'
    
    oc = OddsCalculator(model_path,scaler_path)
    
    odds,val = oc.payout(data,bet_time,100,1,pred_result)
    print(odds,val)
    
    
    
