# DotaBet - Interactive discord bot allowing people to bet on their friends' Dota2 matches 

# _Currently not available for open-access due to costs and scalability issues which will be resolved.

The bot was inspired by the habit of me and my friends to watch each other play Dota2 in discord through discord's streaming functionality. When watching these games we always wanted the ability to predict the outcome, or bet on if we believed our friends were going to win and lose the game. Using a virtual currency and DotaBet this can now happen. 

# How it works 

The bot interacts with OpenDota's API to obtain match data shared by users, parsing the latest games and data to obtain as close to real-time data as possible. Players share their information with DotaBet allowing other discord users to bet on the player by simply mentioning them in discord via an @user call in a text channel. 

The bettor can then specify a win/loss prediction and a value they will choose to bet. 

DotaBet can then place the bet in 'real-time' retrospectively. Data for the match will be available until after the game is over but by storing the time at which the bet was placed, it functions as in-play betting, subject to some minor constraints for stability. 

In order to offer an interactive experience, DotaBet will also offer real-time varying odds (albeit unknown to the bettor at the time of the bet). This is done by parsing the data from the game obtaining statistics about the state of the game at the given time (specifically, gold and xp advantages at that time). Then by feeding this data to a pre-trained (by myself on collected match data) nerual network, a probability prediction (in the range [0,1]) is given expressing the Radiant team's likelihood of winning. This probability is then translated into odds for the respective bet via simple formulas. This process is illustrated below:

<img width="925" alt="Screenshot 2022-05-05 at 12 50 01" src="https://user-images.githubusercontent.com/28924135/166917331-f9e61e1d-f4cf-4987-8e6d-0f18f4e38903.png">

While not a perfect predictor of games, the neural network accurately predicts the winner of the game with a cross-validated accuracy of 75%.

The folder includes an additional standalone python module 'dota_client' for interacting with, and extracting data from, OpenDota's API written by myself, designed for the purpose of obtaining and parsing useful data for DotaBet. 


# Example usage 

<img width="471" alt="Screenshot 2022-05-05 at 12 32 25" src="https://user-images.githubusercontent.com/28924135/166914873-a15f07c3-ac0a-4b2a-a5f2-55b104f3434c.png">

<img width="291" alt="Screenshot 2022-05-05 at 12 33 51" src="https://user-images.githubusercontent.com/28924135/166915083-4185bf4e-52eb-4bad-bfd5-bb3146423c55.png">

<img width="450" alt="Screenshot 2022-05-05 at 12 34 05" src="https://user-images.githubusercontent.com/28924135/166915094-b2b733df-31af-4c7e-aba9-a6a09634dc7f.png">


