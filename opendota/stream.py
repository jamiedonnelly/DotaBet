from opendota.client import DotaAPIClient
from opendota.parsing import GameParser
import os 
import queue
import asyncio
import json
import time 
import threading

# A script to be used for streaming parsed match data

# Constants 
SENTINEL = object()
BATCH_SIZE = 250
LIMIT = 1e5
ASYNC_SIGNAL = asyncio.Event()
THREAD_SIGNAL = threading.Event()
FILENAME = "./data/games.json"

client = DotaAPIClient(os.environ["OD_API_KEY"])

async def stream_parsed_match_ids(init_id: str, q: asyncio.Queue):
    params = {"less_than_match_id":init_id}
    while not ASYNC_SIGNAL.is_set():
        try:
            data = await client.get_json_data("parsedMatches", params=params)
            if not data:
                await asyncio.sleep(10)
                continue
            _ids = [i["match_id"] for i in data]
            for _id in _ids:
                await q.put(_id)
            params["less_than_match_id"] = min(_ids)
        except:
            await asyncio.sleep(30)
        await asyncio.sleep(10)
    print("`stream_parsed_match_ids` shutting down...")

async def check_game(q: asyncio.Queue, output: queue.Queue):
    while not ASYNC_SIGNAL.is_set():
        try:
            _id = await asyncio.wait_for(q.get(), timeout=2)
            try:
                _id = await asyncio.wait_for(q.get(), timeout=2)
                data = await client.get_match(_id)
                if data["lobby_type"] not in [0,5,6,7]:
                    continue
                if GameParser.check_early_finish(data):
                    continue
                output.put(data)
            except asyncio.TimeoutError:
                await asyncio.sleep(20)
            except Exception:
                await asyncio.sleep(20)
        except asyncio.TimeoutError:
            await asyncio.sleep(20)
        except Exception:
            await asyncio.sleep(20)
    print("`check_game` shutting down...")

# This goes in one thread
def process_data(q: queue.Queue, output: queue.Queue):
    batch = []
    while not THREAD_SIGNAL.is_set():
        try:
            data = q.get(timeout=30)
            processed = GameParser.parse(data)
            batch.append(processed)
            if len(batch) >= BATCH_SIZE:
                print("Obtained batch of processed games...")
                output.put(batch)
                batch = []
        except queue.Empty as e:
            time.sleep(30)
        except Exception:
            time.sleep(10)
    print("`process_data` shutting down...")

# This goes in another thread
def write_games_to_file(q: queue.Queue):
    counter = 0
    while True:
        if counter >= LIMIT:
            ASYNC_SIGNAL.set()
            THREAD_SIGNAL.set()
            break
        try:
            batch = q.get(timeout=120)
            with open(FILENAME, "a") as f:
                json_strings = [json.dumps(item) + "\n" for item in batch]
                f.writelines(json_strings)
            counter += len(batch)
            print(f"{counter} games written to file...")
        except queue.Empty as e:
            time.sleep(60)
        except Exception:
            time.sleep(10)
    print("Limit reached, `write_games_to_file` is shutting down...")

# main
async def main():

    # This is for restarting 
    try:
        _ids = []
        with open("./data/games.json","r") as f:
            for line in f.readlines():
                _ids.append(json.loads(line)["match_id"])
        init_id = min(_ids)
    except:
        init_id = await client.get_recent_id()

    # Init queues
    parsed_ids_queue = asyncio.Queue()
    correct_game_queue = queue.Queue()
    processed_games_queue = queue.Queue()

    # Number of worker threads for checking the games
    num_check_game_workers = 5
    # Number of workers for processing data
    num_process_data_threads = 5

    # Init worker threads
    process_data_threads = [threading.Thread(target=process_data, args=(correct_game_queue, processed_games_queue)) for _ in range(num_process_data_threads)]
    for thread in process_data_threads:
        thread.start()

    write_to_file_thread = threading.Thread(target=write_games_to_file, args=(processed_games_queue,))
    write_to_file_thread.start()

    # Init async tasks
    retrieve_ids_task = asyncio.create_task(stream_parsed_match_ids(init_id, parsed_ids_queue))
    check_game_tasks = [asyncio.create_task(check_game(parsed_ids_queue, correct_game_queue)) for _ in range(num_check_game_workers)]

    try:
        await asyncio.gather(retrieve_ids_task, *check_game_tasks)
    except Exception as e:
        print(e)
    finally:
        ASYNC_SIGNAL.set()
        THREAD_SIGNAL.set()
        retrieve_ids_task.cancel()
        for task in check_game_tasks:
            task.cancel()
        for thread in process_data_threads:
            thread.join()
        write_to_file_thread.join()

if __name__=="__main__":
    asyncio.run(main())