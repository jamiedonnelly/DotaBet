import os
from tempfile import TemporaryFile
import discord 
from discord.ext import commands 
import requests 
import numpy as np
from datetime import datetime
import asyncio
from functools import wraps
import matplotlib.pyplot as plt 
from modules.balances import Balances, UserInfo
from modules.dota_client import DotaClient
import time 
import pandas as pd
import logging
from modules.reactions import good_react, bad_react

### Set backends and setup logging ###
plt.switch_backend('agg')
logging.basicConfig(filename='gambling.log',level=logging.DEBUG)
logger = logging.getLogger(__name__)
###

class Gambling(commands.Cog):

    def __init__(self, bot, host, user, database, password):
        self.bot = bot 
        self.host, self.user, self.database, self.password = host, user, database, password
        self.balance = Balances(self.host, self.user, self.database, self.password)
        self.userinfo = UserInfo(self.host, self.user, self.database, self.password)
        self.dotaclient = DotaClient({api_key})

    async def ex_bet(self,ctx):
        description = "$bet @player W 1000"
        embed = discord.Embed(title="Example bet", description="An example use of the 'bet' functionality is outlined below.", color=0x0040ff)
        embed.add_field(name="Command",value=description)
        await ctx.channel.send(embed=embed)
        
    @commands.command()
    async def example(self,ctx):
        await self.ex_bet(ctx)
        return
    
    @commands.command()
    async def steamconfig(self,ctx,arg):
        try:
            steam_id = int(arg)
            user_id = ctx.author.id 
            self.userinfo.config_steam(user_id, steam_id)
            await ctx.message.add_reaction("✅")
        except ValueError as e:
            logging.warning(e)
            embed = discord.Embed(name="Steam Config Error",description="Steam ID must be a number.",color=0xff0000)
            await ctx.message.add_reaction("❌")
            ctx.reply(embed=embed)
            return
        
    async def guild_users(self,ctx):
        ids = []
        for member in ctx.guild.members:
            ids.append(member.id)
        return ids
        
    @commands.command()
    async def configured(self,ctx):
        guild_members = self.guild_users(ctx)
        users = [i for i in self.userinfo.get_all_configured_users() if i in guild_members]
        embed = discord.Embed(title='Configured users',description='list of users with configured steam profiles',color=0x0040ff)
        for i in range(len(users)):
            embed.add_field(name="User",value="<@{}>".format(np.int64(users[i])),inline=False)
        await ctx.channel.send(embed=embed)
    
    def _id(self,user:str):
        user = user.replace("<","")
        user = user.replace(">","")
        user = user.replace("!","")
        user = user.replace("@","")
        return user 
    
    @commands.command()
    async def leaderboard(self,ctx):
        ids = []
        for member in ctx.guild.members:
            ids.append(member.id)
        ids = np.array(ids)
        balances = np.array([float(self.balance.get_balance(i)) for i in ids])
        dt = pd.DataFrame(index=[i for i in range(len(balances))],columns=['id','balance'])
        dt['id']=ids
        dt['balance'] =balances
        dt.sort_values(by='balance',inplace=True, ascending=False)
        embed = discord.Embed(title="Leaderboard",description="Players with current highest balances.",color=0x0040ff)
        if len(ids)<5:
            num=len(ids)
        else:
            num=5
        for i in range(num):
            embed.add_field(name="{}".format(dt.iloc[i,1]),value='<@{}>'.format(dt.iloc[i,0]),inline=False)
        await ctx.channel.send(embed=embed)        
        
    async def losing_bet(self,ctx,player,pred_result,bet,new_balance):
        description = "Losing bet! {} bet on {} to {} and lost!".format(ctx.author.mention, player, pred_result)
        embed = discord.Embed(title="Losing Bet", description=description, color=0x000000)
        embed.set_image(url=bad_react())
        embed.add_field(name="Bet Value", value=str(bet), inline=True)
        embed.add_field(name="New Balance", value=str(new_balance), inline=True)
        await ctx.channel.send(embed=embed)    
        
    async def winning_bet(self,ctx,player,pred_result,bet,new_balance):
        description = "Winning bet! {} bet on {} to {} and won!".format(ctx.author.mention, player, pred_result)
        embed = discord.Embed(title="Winning Bet", description=description, color=0xffffff)
        embed.set_image(url=good_react())
        embed.add_field(name="Bet Value", value=str(bet), inline=True)
        embed.add_field(name="New Balance", value=str(new_balance), inline=True)
        await ctx.channel.send(embed=embed)
        
    def refund(self,bettor_id,value):
        self.balance.new_entry(bettor_id,value)
        return
                                
    @commands.command()
    async def bet(self, ctx, player, outcome, bet):
        try:
            # check validity of the bet being placed - outcome must be a win or a loss
            if not ((outcome.strip().upper()=="W") or (outcome.strip().upper()=="L")):
                embed = discord.Embed(title="Syntax Error",description="Syntax incorrect. Outcome of the match must be specified as W/L.",color=0xff0000)
                await ctx.message.add_reaction("❌")
                await ctx.reply(embed=embed)
                return 
            
            bet = float(bet)
            bet_time = time.time()
            bettor_id = ctx.author.id
            player_disc_id = self._id(player)
            
            print("{} bet on {} to {}".format(ctx.author,player_disc_id,outcome))

            if await self.check_bet(ctx,bet):
                self.balance.new_entry(bettor_id,-1*bet)
                if outcome.strip().upper()=="W":
                    pred_result = "win"
                else:
                    pred_result = "lose"
                
                try:
                    id = self.userinfo.get_steam_id(player_disc_id)
                except:
                    embed = discord.Embed(title="Configuration Error",description="{} has not configured their steam profile.".format(player),color=0xff0000)
                    self.refund(bettor_id,bet)
                    await ctx.message.add_reaction("❌")
                    await ctx.reply(embed=embed)
                    return
                
                try:
                    await ctx.message.add_reaction("⏳")
                    latest_id = await asyncio.wait_for(asyncio.gather(self.dotaclient.wait_new_match(id)),timeout=60*110)
                    latest_game = self.dotaclient.get_match_by_id(latest_id[0])
                except asyncio.TimeoutError:
                    embed = discord.Embed(title="Match Error",description="No game was found within acceptable time period.",color=0xff0000)
                    self.refund(bettor_id,bet)
                    await ctx.reply(embed=embed)
                    await ctx.message.add_reaction("❌")         
                    return  


                if self.check_bet_time(latest_game,bet_time):
                    
                    team = self.dotaclient.get_player_team(latest_game['match_id'],id)
                    
                    if (team==1) & (latest_game['radiant_win']==True) & (pred_result=="win"):
                        self.balance.new_entry(bettor_id,2*bet)
                        new_balance = self.balance.get_balance(bettor_id)
                        await self.winning_bet(ctx, player, pred_result, bet, new_balance)
                        await ctx.message.add_reaction("✅")
                        return
                    elif (team==-1) & (latest_game['radiant_win']==False) & (pred_result=="win"):
                        self.balance.new_entry(bettor_id,2*bet)
                        new_balance = self.balance.get_balance(bettor_id)
                        await self.winning_bet(ctx, player, pred_result, bet, new_balance)
                        await ctx.message.add_reaction("✅")
                        return
                    elif (team==1) & (latest_game['radiant_win']==False) & (pred_result=="lose"):
                        self.balance.new_entry(bettor_id,2*bet)
                        new_balance = self.balance.get_balance(bettor_id)
                        await self.winning_bet(ctx, player, pred_result, bet, new_balance)
                        await ctx.message.add_reaction("✅")
                        return
                    elif (team==-1) & (latest_game['radiant_win']==True) & (pred_result=="lose"):
                        self.balance.new_entry(bettor_id,2*bet)
                        new_balance = self.balance.get_balance(bettor_id)
                        await self.winning_bet(ctx, player, pred_result, bet, new_balance)
                        await ctx.message.add_reaction("✅")
                        return
                    else:
                        new_balance = self.balance.get_balance(bettor_id)
                        await self.losing_bet(ctx, player, pred_result, bet, new_balance)
                        await ctx.message.add_reaction("✅")
                        return
                else:
                    embed = discord.Embed(title="Bet Time Error",description="Bet was placed outside of time limits. Best must be placed 10 minutes prior or up to the first ~5 minutes.",color=0xff0000)
                    embed.add_field(name="Game start time",value=str(datetime.utcfromtimestamp(latest_game['start_time'])),inline=True)
                    embed.add_field(name="Game finish time",value=str(int(datetime.utcfromtimestamp(latest_game['start_time']+latest_game['duration'])),inline=True))
                    embed.add_field(name="Bet time",value=str(int(datetime.utcfromtimestamp(bet_time))),inline=False)
                    self.refund(bettor_id,bet)
                    await ctx.reply(embed=embed)
                    await ctx.message.add_reaction("❌")
            else:
                await ctx.message.add_reaction("❌")
                return
        except Exception as e:
            print(e)
            logging.error(e)
            self.refund(bettor_id,bet)
            await ctx.message.add_reaction("❌")
                    
        
    @commands.command()
    async def echo(self,ctx, *args):
        reply = " ".join([i for i in args])
        embed = discord.Embed(title="Echo",description=reply,color=0x0040ff)
        await ctx.channel.send(embed=embed)
        
    @commands.command()
    @commands.cooldown(1, 60*60*24*3, commands.BucketType.user)
    async def refresh(self,ctx):
        self.balance.reset_balance(ctx.author.id)
        balance = self.balance.get_balance(ctx.author.id)
        embed = discord.Embed(title="Refresh Balance",color=0x0040ff)
        embed.add_field(name="Balance",value=str(balance))
        await ctx.reply(embed=embed)
        return
    
    @commands.Cog.listener()
    async def on_member_join(self,member):
        user_id = member.id 
        self.balance.new_user(user_id)
        
    @commands.Cog.listener()
    async def on_guild_join(self,guild):
        for member in guild.members:
            self.balance.new_user(member.id)
        
    @commands.Cog.listener()
    async def on_guild_remove(self,guild):
        for member in guild.members:
            self.balance.remove_user(member.id)
        
    @commands.Cog.listener()
    async def on_member_remove(self,member):
        user_id = member.id
        self.balance.remove_user(user_id)
        self.userinfo.drop_user(user_id)
    
    async def check_bet(self,ctx,bet):
        user_id = ctx.author.id
        bet = float(bet)   
        if bet <=0: 
            embed = discord.Embed(title="Bet Error",description="Bet value must be greater than 0.",color=0xff0000)
            await ctx.reply(embed=embed)
            await ctx.message.add_reaction("❌")
            return False
        balance = self.balance.get_balance(user_id)
        if bet > balance:
            embed = discord.Embed(title="Bet Error",description="Bet exceeds current balance of {}".format(balance),color=0xff0000)
            await ctx.reply(embed=embed)
            await ctx.message.add_reaction("❌")
            return False
        return True 

    def check_bet_time(self, game_data, time):
        match_start = game_data['start_time']
        duration = game_data['duration']
        if (time >= (match_start-300)) & (time <= (match_start + duration)):
            return True 
        else:
            return False
            
    @commands.command()
    async def balance(self,ctx):
        user_id = ctx.author.id 
        balance = self.balance.get_balance(user_id)
        entries = self.balance.get_entries(user_id)
        plt.figure()
        plt.plot([datetime.utcfromtimestamp(i) for i in entries[:,0]],entries[:,2])
        plt.xlabel("Date")
        plt.ylabel("Balance")
        plt.title("{} balance over time".format(ctx.author))
        plt.xticks([])
        plt.savefig('plot.png')
        file = discord.File('plot.png',filename='image.png')
        embed = discord.Embed(color=0x002aff)
        embed.set_image(url="attachment://image.png")
        embed.add_field(name="{}'s Balance".format(ctx.author), value=str(balance), inline=True)
        await ctx.channel.send(file=file,embed=embed)

def setup(bot,host,user,database,password):
    bot.add_cog(Gambling(bot,host,user,database,password))