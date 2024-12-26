import sys
import time
import aiohttp
import re
import os
import asyncio
import argparse
import logging
import m3u8_To_MP4


LINK_PATTERN = r'contentUrl"\s*:\s*"([^"]+)'
FORMAT_PATTERN = r'fileFormat"\s*:\s*"([^"]+)'
MAX_RETRIES = 3
RETRY_DELAY = 1


async def get_link(episode: str, session: aiohttp.ClientSession):
    async with session.get(f'https://sp.freehat.cc/episode/{episode}/') as response:
        html = await response.text()

        try:
            return re.findall(LINK_PATTERN, html)[0]
        except IndexError:
            return None


async def download_episode_mp4(link: str, session: aiohttp.ClientSession):
    filename = os.path.join('./south_park/', link.split("/")[-1])
    os.makedirs('./south_park/', exist_ok=True)

    retries = 0
    while retries <= MAX_RETRIES:
        try:
            async with session.get(link) as response:
                response.raise_for_status()

                total_size = int(response.headers.get('Content-Length', 0))
                downloaded = 0

                with open(filename, "wb") as f:
                    while chunk := await response.content.read(1024):
                        f.write(chunk)
                        downloaded += len(chunk)

                        progress = (downloaded / total_size) * 100 if total_size > 0 else 0

                        sys.stdout.write("\rDownloading: [{:<50}] {:.2f}%".format("#" * int(progress // 2), progress))
                        sys.stdout.flush()

                print(f"\nDownloaded: {filename}")
                return

        except Exception as e:
            retries += 1
            logging.error(f"Attempt {retries}/{MAX_RETRIES} failed to download {link}: {e}")
            if retries < MAX_RETRIES:
                logging.info(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                logging.error(f"Failed to download {link} after {MAX_RETRIES} attempts.")

    logging.error(f"Failed to download {link} after {MAX_RETRIES} retries.")


async def download_episode_m3u8(link: str, session: aiohttp.ClientSession):
    filename = link.split('/')[-1].split('.')[0]
    logging.info(f'Downloading {filename} from m3u8')
    m3u8_To_MP4.multithread_download(link, mp4_file_dir='south_park', mp4_file_name=filename)
    logging.info(f'Downloaded {filename} successfully.')


download_mapper = {
    'mp4': download_episode_mp4,
    'm3u8': download_episode_m3u8,
}


async def download_episodes(episodes: list[str]):
    async with aiohttp.ClientSession() as session:
        links = await asyncio.gather(
            *(get_link(episode, session) for episode in episodes),
        )

        error_episodes = []
        for link in links:
            if link is None:
                continue

            file_format = link.split('.')[-1]

            try:
                await download_mapper[file_format](link, session)
            except KeyError:
                logging.error(f'Unsupported format: {file_format}')
                error_episodes.append(link.split('/')[-1])

    logging.info(f'Failed to download: {error_episodes}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(dest='episodes', nargs='+', type=str)
    args = parser.parse_args()

    asyncio.run(download_episodes(args.episodes))
