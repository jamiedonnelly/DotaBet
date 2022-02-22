#### Reaction images

import random

def good_react():
    good_reacts = ["https://c.tenor.com/TVrgcpGhWkIAAAAd/impressive-very-nice.gif",
               "https://media4.giphy.com/media/kYsBThMhhalLG/giphy.gif?cid=ecf05e47ykm9pi9yucdqojlwupn2nd80klmo0d8fuohgpl31&rid=giphy.gif&ct=g",
                "https://i.dailymail.co.uk/1s/2021/07/02/11/44955235-9749253-image-a-58_1625223318420.jpg",
                "https://screenqueens.files.wordpress.com/2016/11/2016-05-12-1463094647-2484649-amerpsycho_208pyxurz1.jpg?w=720"
    ]
    ran = random.randint(0,len(good_reacts)-1)
    return good_reacts[ran]

def bad_react():
    lose_reacts = ["https://streamsentials.com/wp-content/uploads/sadge-png.png" ,
               "https://steamuserimages-a.akamaihd.net/ugc/1702906068187274429/840C8933F7109AF7FBF658B8BFDD12147774371D/?imw=512&&ima=fit&impolicy=Letterbox&imcolor=%23000000&letterbox=false",
                "https://streamsentials.com/wp-content/uploads/pepehands-transparent-pic.png",
                "https://p.favim.com/orig/2018/08/26/reaction-pic-reaction-memes-Favim.com-6188975.jpg",
                "https://preview.redd.it/59ck9ag194a71.jpg?width=640&crop=smart&auto=webp&s=bc5c60f09a4463b24701a850c1850a41abcf9764"
    ]
    ran = random.randint(0,len(lose_reacts)-1)
    return lose_reacts[ran]