"""
Leaguepedia mwclient examples ported to the aiomwclient
https://lol.fandom.com/wiki/Help:Leaguepedia_API#Sample_Code
"""
import asyncio

import aiomwclient


async def main():
    site: aiomwclient.Site = await aiomwclient.Site().init(
        "lol.fandom.com", path="/", scheme="https"
    )

    # EXAMPLE 1: Basic search
    print("---- Example 1 ----")
    response = await site.api(
        "cargoquery",
        limit="10",
        tables="ScoreboardGames=SG",
        fields="SG.Tournament, SG.DateTime_UTC, SG.Team1, SG.Team2",
    )
    print(response)

    # EXAMPLE 2: Results before/after date
    print("---- Example 2 ----")
    response = await site.api(
        "cargoquery",
        limit="10",
        tables="ScoreboardGames=SG",
        fields="SG.Tournament, SG.DateTime_UTC, SG.Team1, SG.Team2",
        where="SG.DateTime_UTC >= '2019-08-08' AND SG.DateTime_UTC <= '2019-08-10'",  # Results after Aug 8, 2019 and before or during Aug 1-, 2019
    )
    print(response)

    # EXAMPLE 3: Multiple table search
    print("---- Example 3 ----")
    page_to_query = "Data:2019 Mid-Season Invitational/Play-In"
    response = await site.api(
        "cargoquery",
        limit=3,
        tables="MatchScheduleGame=MSG,MatchSchedule=MS",
        fields="MSG.OverviewPage, MSG.MatchHistory",
        where=r'MSG._pageName="%s" AND MSG.MatchHistory IS NOT NULL AND NOT MSG.MatchHistory RLIKE ".*(lpl|lol)\.qq\.com.*"'
        % page_to_query,
        join_on="MSG.UniqueMatch=MS.UniqueMatch",
        order_by="MS.N_Page,MS.N_MatchInPage, MSG.N_GameInMatch",
    )
    print(response)

    import datetime as dt

    # EXAMPLE 4: Results in a day, joining ScoreboardGames and ScoreboardPlayers
    print("---- Example 4 ----")
    date = "2020-01-25"
    date = dt.datetime.strptime(date, "%Y-%m-%d").date()

    response = await site.api(
        "cargoquery",
        limit="10",
        tables="ScoreboardGames=SG, ScoreboardPlayers=SP",
        join_on="SG.UniqueGame=SP.UniqueGame",
        fields="SG.Tournament, SG.DateTime_UTC, SG.Team1, SG.Team2, SG.Winner, SG.Patch, SP.Link, SP.Team, SP.Champion, SP.SummonerSpells, SP.KeystoneMastery, SP.KeystoneRune, SP.Role, SP.UniqueGame, SP.Side",
        where="SG.DateTime_UTC >= '"
        + str(date)
        + " 00:00:00' AND SG.DateTime_UTC <= '"
        + str(date + dt.timedelta(1))
        + " 00:00:00'",
    )
    print(response)

    # EXAMPLE 5: Save Player image
    print("---- Example 5 ----")
    import json
    import re

    import aiohttp

    async def get_filename_url_to_open(site, filename, player, size=None):
        pattern = r".*src\=\"(.+?)\".*"
        size = "|" + str(size) + "px" if size else ""
        to_parse_text = "[[File:{}|link=%s]]".format(filename, size)
        result = await site.api(
            "parse", title="Main Page", text=to_parse_text, disablelimitreport=1
        )
        parse_result_text = result["parse"]["text"]["*"]

        url = re.match(pattern, parse_result_text)[1]
        # In case you would like to save the image in a specific location, you can add the path after 'url,' in the line below.
        # urllib.request.urlretrieve(url, player + ".png")
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                with open(player + ".png", "wb") as file:
                    file.write(await resp.read())

    player = "Perkz"

    response = await site.api(
        "cargoquery",
        limit=1,
        tables="PlayerImages",
        fields="FileName",
        where='Link="%s"' % player,
        format="json",
    )
    parsed = json.dumps(response)
    decoded = json.loads(parsed)
    url = str(decoded["cargoquery"][0]["title"]["FileName"])
    await get_filename_url_to_open(site, url, player)
    print(f"{url} -> {player}.png")

    # Close the site once we're done with it
    await site.close()


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
