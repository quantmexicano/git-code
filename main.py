
from telethon import TelegramClient, events
from config import api_id, api_hash
from channel_map_file import channel_map
import socks # Adding import for the socks library
import json
import asyncio
import logging

logging.basicConfig(format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s', level=logging.INFO) # Setting INFO for details

client = TelegramClient(
    'sessionname_session',
    api_id,
    api_hash,
    proxy=(socks.SOCKS5, '555.111.99.88', 2030, True, 'newusername', 'newpassword123')
)
message_map_file = 'message_map.json'

def load_message_map(): 
    try:
        with open(message_map_file, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"File '{message_map_file}' does not exist. Creating a new map.")
        return {}
    except json.JSONDecodeError:
        print(f"Error reading file: '{message_map_file}'. File is corrupted or empty. Creating a new map.")
        return {}
    
def update_message_map(message_map):
    with open(message_map_file, 'w') as file:
        json.dump(message_map, file, indent=4)

# Adding new variables

media_group = []
media_group_id = None
media_group_timer = None

# Adding function to send media group
async def send_media_group(mirchan, rplid, disable_web_page_preview):
    global media_group, media_group_id
    # Adding variable copied_message to return result
    copied_message = None
    if media_group:
        media = []
        text = None
        for event in media_group:
            if event.message.media:
                media.append(event.message.media)
            if event.message.text:
                text = event.message.text   # Taking text from the last message
        if media:
            try:
                # Adding text truncation
                if text and len(text) > 1024:
                    logging.warning(f"Text is too long ({len(text)} characters). Trimming to 1024 characters.")
                    text = text[:1021] + "..."
                copied_message = await client.send_file(
                    mirchan,
                    media,
                    caption=text or "",  # If there is no text, use an empty string
                    reply_to=rplid,
                    link_preview=not disable_web_page_preview 
                )
                logging.info(f"Sent media group with {len(media)} items.")
            except Exception as e:
                logging.error(f"Error sending media group to {mirchan}: {e}")
        else:
            logging.warning("Unable to retrieve media files for the group.")

        media_group = []
        media_group_id = None
    # Adding return of copied_message variable
    return copied_message

# Listener for new messages in source channels

@client.on(events.NewMessage(chats=list(channel_map.keys())))
async def listener(event):

    # Using global variables

    global media_group, media_group_id, media_group_timer

    source = event.chat_id
    mirchan = channel_map.get(source)

    if not mirchan:
        logging.warning(f"No destination channel found for source {source}. Skipping.")
        return

    message_map = load_message_map()

    source_data = message_map.setdefault(str(source), {"messages": {}, "last_processed_msg_id": 0})
    if event.message.id <= source_data["last_processed_msg_id"]:
        logging.info(f"Message {event.message.id} from {source} already processed. Skipping.")
        return
    
    logging.info(f"Processing message {event.message.id} from source {source}.")
    logging.info(f"Message тэкст: '{event.message.text}' (type: {type(event.message.text)})")
    logging.info(f"Message media: '{event.message.media}' (type: {type(event.message.media)})")
   
    copied_message = None
    rplid = None
    disable_web_page_preview = False
    if event.message.text and ("http://" in event.message.text or "https://" in event.message.text):
        disable_web_page_preview = True

    if event.message.reply_to:
        orpl = event.message.reply_to.reply_to_msg_id
        if orpl:
            crpl = source_data["messages"].get(str(orpl))
            if crpl:
                rplid = crpl
                logging.info(f"Sending reply to message {orpl} (copied ID: {crpl}) from channel {source}")
            else:
                logging.warning(f"Original message for reply {orpl} not found in map {message_map_file}. Copying simple message.")

    else:
        logging.info(f"Sending simple message {event.message.id} from channel {source}")
                
    try:
        if event.grouped_id:  #5
            if media_group_id == event.grouped_id:  #6
                media_group.append(event)   #7
            else: #8
                if media_group_timer:  #9
                    media_group_timer.cancel() #10
                await send_media_group(mirchan, rplid, disable_web_page_preview) #11
                media_group = [event]  #12
                media_group_id = event.grouped_id  #13

            if media_group_timer:  #14
                media_group_timer.cancel() #15
            loop = asyncio.get_event_loop()  #16
            media_group_timer = loop.call_later(0.5, asyncio.ensure_future, send_media_group(mirchan, rplid, disable_web_page_preview)) #17
            return  #18
        
        else: #19
            if media_group_timer:  #20
                media_group_timer.cancel() #21

            # Replacing call to send media group function

            copied_message = await send_media_group(mirchan, rplid, disable_web_page_preview) #22
           
            if event.message.media: #23
                # Adding media type check
                if hasattr(event.message.media, 'document'):
                    logging.info(f"Detected document/video. Mime type: {event.message.media.document.mime_type}")
                # Adding cutting long text
                text = event.message.text
                if text and len(text) > 1024:
                    logging.warning(f"Text is too long ({len(text)} characters). Trimming to 1024 characters.")
                    text = text[:1021] + "..."
                copied_message = await client.send_file(
                    mirchan,
                    file=event.message.media,
                    caption=event.message.text or "", # <--- If there is no text, use an empty string
                    reply_to=rplid,
                    link_preview=not disable_web_page_preview 
                )
                logging.info(f"Sent document/video with caption: '{event.message.text[:50]}...'")
            elif event.message.text:
                logging.info(f"Detected only text.")
                copied_message = await client.send_message(
                    mirchan,
                    event.message.text,
                    reply_to=rplid,
                    link_preview=not disable_web_page_preview 
                )
                logging.info(f"Sent only text: '{event.message.text[:50]}...'")
            else:
                logging.warning(f"Message {event.message.id} from {source} has no supported content (neither photo, nor video/document, nor text). Skipping.")
        await asyncio.sleep(1)  # wait to avoid FloodWait
    except Exception as e:
        logging.error(f"Error sending message to channel {mirchan}: {e}", exc_info=True) # exc_info=True for full stack trace

    if copied_message:
        source_data["messages"][str(event.message.id)] = copied_message.id
        source_data["last_processed_msg_id"] = event.message.id
        update_message_map(message_map)
        logging.info(f"Copied message from {source} (ID: {event.message.id}) to {mirchan} (ID: {copied_message.id})")
        await asyncio.sleep(1) # Wait to avoid FloodWait
    else:
        logging.warning(f"Message {event.message.id} from {source} was not copied due to an error.")
  
async def main():
    await client.start()
    print("Connection established")
    print("Bot is running and listening for new messages....")
    await client.run_until_disconnected()
    logging.info("Bot stopped.")

if __name__ == '__main__':
    asyncio.run(main())
