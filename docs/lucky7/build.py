"""Build the Lucky Seven series docs (one rendered doc per episode) from the scripts below.

    python docs/lucky7/build.py

Writes docs/lucky7-<n>-<state>/lines.json and broll_queries.json. Each episode renders on its own
(docs.yml); the full film is stitched afterward from the episodes' voices and pictures.
Script lines: (speaker, text, visual). Visual: a broll stem "<key>-<n>", "card:Title|Sub", or None.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def anchor(key, name, desk, piper="en_US-ryan-high"):
    # the cloned audition voice when voices/anchors/<key>.ogg exists, else this Piper voice
    return {"name": name, "ref": f"voices/anchors/{key}.ogg", "avatar": f"anchors/{key}.webp",
            "desk": f"{desk} desk · AI anchor", "piper": piper}


VOICES = {
    "M": {"name": "MATTHEW", "ref": "matthew", "piper": "en_US-ryan-high"},
    "G": anchor("bowling-green", "GARY MERCER", "Bowling Green"),
    "YA": anchor("yale", "THURSTON WHITMORE", "Yale", "en_GB-alan-medium"),
    "BR": anchor("brown", "BARNABY THAYER", "Brown", "en_GB-northern_english_male-medium"),
    "CO": anchor("columbia", "HENRIETTA MORNINGSIDE", "Columbia", "en_GB-jenny_dioco-medium"),
    "CR": anchor("cornell", "LIBBY HARTWELL", "Cornell", "en_US-amy-medium"),
    "HA": anchor("harvard", "PRUDENCE ASHWORTH", "Harvard", "en_US-kristin-medium"),
    "DA": anchor("dartmouth", "WINNIE HOLLIS", "Dartmouth", "en_US-hfc_female-medium"),
    "PR": anchor("princeton", "CHIP VAN DOREN", "Princeton", "en_US-joe-medium"),
    "PE": anchor("penn", "BENJAMIN QUILL", "Penn", "en_GB-alan-medium"),
}

EPISODES = []


def ep(n, slug, state, title, queries, lines):
    EPISODES.append(dict(n=n, slug=slug, state=state, title=title, queries=queries, lines=lines))


# ---------------------------------------------------------------- 1. Connecticut
ep(1, "ct", "Connecticut", "The Cane and the Tongs", [
    ["ct-capitol", "Connecticut State Capitol Hartford"],
    ["ct-yale", "Yale Old Campus Connally"],
    ["ct-yale-old", "Yale College 1786 engraving"],
    ["ct-griswold", "Roger Griswold portrait"],
    ["ct-pugilists", "Congressional Pugilists 1798 cartoon"],
    ["ct-lyon", "Matthew Lyon portrait congressman"],
    ["ct-hall", "Congress Hall Philadelphia"],
    ["ct-lyme", "Old Lyme Connecticut"],
    ["ct-blackhall", "Griswold house Old Lyme Florence"],
    ["ct-norwich", "Norwich Connecticut historic"],
    ["ct-griswold-town", "Griswold Connecticut Jewett City"],
    ["ct-adams", "John Adams portrait Gilbert Stuart"],
    ["ct-sedition", "Sedition Act 1798"],
    ["ct-vergennes", "Vergennes Vermont"],
    ["ct-ivy", "Ivy League map"],
], [
    # film open (narration only; plates are added when the film is stitched)
    ("M", "Eight schools. Seven states. The Ivy League has trained presidents, justices, and a long line of governors. Tonight we are not going after the famous ones.", "ct-ivy-1"),
    ("M", "Here is the game. Take the seven states that hold an Ivy League school. Count the governors from independence. Stop at number seven. Seven governors, seven minutes each, seven facts each. Lucky seven.", "card:Lucky Seven|The seventh governors of the Ivy states"),
    ("M", "And every episode asks the same three questions. Who got a say. Who got left out. And who paid for it.", "card:Who got a say?|Who got left out? Who paid for it?"),
    ("G", "Matthew, I'm a Bowling Green guy. I know one governor from back east, and he was on the money.", None),
    ("M", "Then you are going to learn six new ones, Gary. We start in Connecticut.", "ct-capitol-1"),
    ("CHAP", "", "card:Chapter One · Connecticut|Roger Griswold · Yale, class of 1780"),
    # 1 cold open
    ("M", "Philadelphia. The winter of 1798. The United States Congress meets in Congress Hall, next to the State House. It is a young country, and the men in this room still treat it like a gentlemen's club.", "ct-hall-1"),
    ("M", "On January 30th, in a session on the House floor, Congressman Matthew Lyon of Vermont and Congressman Roger Griswold of Connecticut trade insults. Griswold asks him, mockingly, whether he'll be using his wooden sword, a jab at a disputed story that Lyon was drummed out of a command in the Revolution. Lyon spits tobacco juice in his face.", "ct-lyon-1"),
    ("M", "Two weeks later, February 15th, Griswold walks onto the floor with a hickory walking stick and goes after Lyon with it. Lyon grabs a pair of fireplace tongs from the hearth and fights back, right there, in the House of Representatives.", "ct-pugilists-1"),
    ("G", "Now hold on. Fireplace tongs? In Congress?", None),
    ("YA", "Old boy, it was February. There was a fire. One makes do.", None),
    ("M", "That is the man who would become Connecticut's seventh governor. And who he hit matters. Because Matthew Lyon was not a gentleman. Matthew Lyon had arrived in this country as a teenager who owed for his own passage.", "card:Fact 1 of 7|In 1798 Roger Griswold attacked a congressman with a cane on the House floor"),
    # 2 where he came from
    ("M", "Roger Griswold was born May 21st, 1762, in Lyme, Connecticut, at the mouth of the Connecticut River. He was born into the governing class, and not by accident.", "ct-lyme-1"),
    ("M", "His father, Matthew Griswold, became governor of Connecticut. His mother's father, Roger Wolcott, had been the colonial governor. Three generations, one family, one office.", "card:Fact 2 of 7|His father and his grandfather were both governors of Connecticut"),
    ("M", "He entered Yale at fourteen and graduated in 1780, during the Revolution. Then he read law, and the law led where it always led for a family like his. Into politics.", "ct-yale-old-1"),
    ("YA", "Fourteen is young for Yale, I grant you. But the Griswolds were always early. To everything.", None),
    ("G", "Must be nice to have a reserved seat.", None),
    # 3 the climb
    ("M", "Griswold went to Congress in 1795, a Federalist, the party of merchants, bankers and old New England families. He was sharp, he was proud, and he did not like the new men from the frontier.", "ct-griswold-1"),
    ("M", "Matthew Lyon was the new man from the frontier. Born in Ireland in 1749. He came to Connecticut in 1764, around fifteen years old, as a redemptioner. That means he couldn't pay for the ship, so his labor was sold to cover it. He worked off that debt for years before he bought his freedom in 1768.", "ct-lyon-2"),
    ("M", "Lyon went north to Vermont, served with the Green Mountain Boys in the Revolution, built a gristmill, a sawmill and a paper mill, started a newspaper, and got himself elected to Congress. A bound laborer who became a congressman. To a Yale man, that was the insult.", "card:Fact 3 of 7|Matthew Lyon came to America owing for his passage and worked it off as a bound laborer"),
    ("M", "After the brawl, a House committee recommended that both men be censured. The full House voted it down. Both men promised to keep the peace. Lyon apologized in writing.", "ct-pugilists-2"),
    ("G", "So nobody got punished.", None),
    ("M", "Not that day, Gary. Wait for it.", None),
    # 4 number seven
    ("M", "Now, the counting. Connecticut's official list of governors goes all the way back to the colony's first governor, in 1639. On that list, Roger Griswold is number twenty-two.", "card:Connecticut's official count|Starts in 1639 · Griswold is No. 22"),
    ("M", "But our game starts at independence. Jonathan Trumbull was governor when the colony became a state. Count from Trumbull, and you get Matthew Griswold, Samuel Huntington, Oliver Wolcott, Jonathan Trumbull Junior, John Treadwell, and then, number seven, Roger Griswold.", "card:Fact 4 of 7|Counted from independence, Roger Griswold is Connecticut's seventh governor"),
    ("YA", "Twenty-second or seventh. Either way, a Griswold. The club does keep its records.", None),
    ("M", "Who gets counted is always a choice somebody made. Keep that in your pocket. It comes back all night.", "ct-capitol-2"),
    # 5 the big swing
    ("M", "Griswold was elected lieutenant governor in 1809 and governor in 1811. He was re-elected in the spring of 1812. And in June of 1812 the United States went to war with Britain.", "ct-griswold-2"),
    ("M", "New England's merchants hated that war. It strangled their trade. So when Washington asked Connecticut for militia, Governor Griswold said no. He refused to put the state's militia under federal command.", "card:Fact 5 of 7|As governor in 1812 he refused to put Connecticut's militia under federal control"),
    ("M", "Remember, this is a man who, back in 1801, turned down John Adams when Adams offered to make him Secretary of War. He did not want to run the federal army. He wanted to keep his own.", "ct-adams-1"),
    ("G", "Hold on. He says no to being in charge of the war, then he says no to the war?", None),
    ("YA", "Consistency, Gary. He simply preferred his militia at home. Near the silver.", None),
    # 6 the twist
    ("M", "Now back to the man with the tongs. That summer of 1798, Congress passed the Sedition Act. It made it a crime to publish false, scandalous or malicious writing against the government.", "ct-sedition-1"),
    ("M", "That October, Matthew Lyon became the first person put on trial under it, for what he had written about President Adams. He was convicted on October 10th, fined a thousand dollars, and locked in a cell in Vergennes, Vermont, for four months.", "card:Fact 6 of 7|Lyon was the first person tried under the Sedition Act · four months in jail, a $1,000 fine"),
    ("M", "And from that cell, the voters of Vermont re-elected him to Congress, four thousand five hundred seventy-six votes to two thousand four hundred forty-four.", "ct-vergennes-1"),
    ("G", "Okay. That's a heck of a comeback.", None),
    ("M", "Same floor, same fight. The gentleman with the cane went home to Connecticut and kept rising. The servant with the tongs went to jail for what he wrote. One law for the club, another for the man who crashed it.", "ct-pugilists-3"),
    ("M", "Roger Griswold did not get long in the governor's chair. He died in office on October 25th, 1812, in Norwich. He was fifty years old.", "ct-norwich-1"),
    # 7 what's left
    ("M", "Three years later, Connecticut named a town for him. Griswold, Connecticut, incorporated in 1815, out in the eastern hills.", "card:Fact 7 of 7|The town of Griswold, Connecticut, incorporated in 1815, is named for him"),
    ("M", "Yale gave him an honorary law degree in 1812, the year he died. His grave is in the family cemetery at Black Hall, in Old Lyme.", "ct-blackhall-1"),
    ("YA", "A Yale man, a Yale father, a governor's grandson. Boola boola, I suppose.", None),
    ("M", "A town for the man with the cane. A jail cell for the man with the tongs. Connecticut's lucky number seven.", "ct-griswold-town-1"),
    ("M", "Connecticut. Keep it real.", "ct-yale-1"),
])

# ---------------------------------------------------------------- 2. Rhode Island
ep(2, "ri", "Rhode Island", "Three Numbers, One Man", [
    ["ri-statehouse", "Rhode Island State House Providence"],
    ["ri-fenner", "James Fenner governor portrait"],
    ["ri-arthur", "Arthur Fenner governor"],
    ["ri-brown", "University Hall Brown University"],
    ["ri-collegehill", "College Hill Providence"],
    ["ri-dorr", "Thomas Wilson Dorr"],
    ["ri-dorr-reb", "Dorr Rebellion"],
    ["ri-arsenal", "Cranston Street Armory Providence arsenal"],
    ["ri-king", "Samuel Ward King governor"],
    ["ri-northburial", "North Burial Ground Providence"],
    ["ri-providence-old", "Providence Rhode Island 19th century engraving"],
    ["ri-charter", "Rhode Island Royal Charter 1663"],
    ["ri-browns", "John Brown House Providence"],
], [
    ("CHAP", "", "card:Chapter Two · Rhode Island|James Fenner · Brown, class of 1789"),
    ("M", "Providence, Rhode Island. May of 1842. The smallest state in the union has two governors at the same time, and only one of them was elected by most of the men who wanted to vote.", "ri-statehouse-1"),
    ("M", "On the night of May 17th, about three hundred men follow a lawyer named Thomas Dorr to the state arsenal in Providence. They bring cannon. The cannon don't fire. The attack falls apart.", "ri-arsenal-1"),
    ("BR", "Bears, class is in session. And today's lesson, kids, is that a revolution needs working artillery.", None),
    ("G", "Two governors? How does a state end up with two governors?", None),
    ("M", "Hold that, Gary. To get there, we start with a man who was governor three separate times, across thirty-eight years. James Fenner. He holds three numbers on Rhode Island's list. Seven, eleven and seventeen.", "card:Fact 1 of 7|James Fenner was governor three times, so he is Rhode Island's 7th, 11th and 17th"),
    # 2 where he came from
    ("M", "James Fenner was born in Providence on January 22nd, 1771. His father, Arthur Fenner, was Rhode Island's fourth governor and held the office for fifteen years, until he died in it.", "ri-arthur-1"),
    ("M", "James went up College Hill to the school then called Rhode Island College. He graduated in 1789. In 1804 the college took the name of a family of Providence merchants. Brown.", "card:Fact 2 of 7|Fenner graduated in 1789 from the college that became Brown University"),
    ("BR", "Ah, the Browns. Now there's a tangent. I do love a tangent.", "ri-browns-1"),
    ("M", "Take the tangent, Barnaby. In 2003 Brown's president, Ruth Simmons, set up a committee to study the university's ties to slavery. Its report came out in 2006. The Brown family profited partly from the transatlantic slave trade. John Brown defended it. His brother Moses became an abolitionist.", "card:Slavery and Justice|Brown University's own report, 2006"),
    ("BR", "To Brown's credit, it asked the question out loud. Most of the club never has.", None),
    # 3 the climb
    ("M", "Fenner rose fast, the way a governor's son does. He went to the United States Senate in 1805. Two years later he resigned the seat to come home and run for governor, and he won.", "ri-fenner-1"),
    ("M", "He served from 1807 to 1811 as a Democratic-Republican. He came back for another long run, 1824 to 1831. Then he stepped away. Rhode Island seemed to be done with him.", "card:Fact 3 of 7|He resigned a U.S. Senate seat in 1807 to become governor"),
    # 4 number seven
    ("M", "Now the count. Rhode Island's list starts in 1775 with Nicholas Cooke. Then William Greene, John Collins, Arthur Fenner. Arthur dies in office in 1805, and two short-term fill-ins, Henry Smith and Isaac Wilbour, each get a full number. That makes James Fenner number seven in 1807.", "card:Fact 4 of 7|Rhode Island gives every stint and every fill-in its own number"),
    ("M", "Rhode Island also hands out a fresh number every time someone comes back. That's how one man ends up with three of them. Count from statehood in 1790 instead, or skip the fill-ins, and number seven is someone else entirely.", "ri-statehouse-2"),
    ("G", "So in Rhode Island the same guy can be seventh, eleventh and seventeenth.", None),
    ("BR", "Small state, Gary. We reuse everything.", None),
    # 5 big swing: the vote
    ("M", "Now, the two governors. In 1841 Rhode Island was still running under its colonial charter from 1663, a document signed by a king. To vote, you had to own land.", "ri-charter-1"),
    ("M", "Factories had filled Providence with working men who owned nothing but their labor. By the 1840s, an estimated six in ten adult white men in Rhode Island could not vote.", "card:Fact 5 of 7|In the early 1840s about 60 percent of Rhode Island's adult white men could not vote"),
    ("M", "So Thomas Dorr and his allies wrote their own People's Constitution, held their own vote, and in April 1842 elected Dorr governor. The old charter government re-elected Samuel Ward King. Two governments. One state.", "ri-dorr-1"),
    ("M", "Then the arsenal. Then the collapse. Dorr was arrested, convicted of treason against Rhode Island in 1844, and sentenced to life. The legislature freed him in 1845.", "ri-dorr-reb-1"),
    ("G", "Life in prison? For wanting a vote?", None),
    # 6 the twist
    ("M", "Here is where the story gets more complicated than heroes and villains. The establishment answered with its own Law and Order Party. And to lead the state under a new constitution, it brought back an old man. James Fenner.", "card:Fact 6 of 7|In 1843 Fenner returned as the Law and Order Party's governor"),
    ("M", "But look closely at Dorr's People's Constitution. It gave the vote to all white men. At its convention, a motion to strike the word white failed, eighteen to forty-six. The people's rebellion left Black men out.", "card:The People's Constitution|Vote to remove the word \"white\": 18 for, 46 against"),
    ("M", "The Law and Order constitution of 1842 did let Black men vote. It also kept a property test for immigrants. Mostly Irish, mostly Catholic, mostly the men in the mills.", "ri-providence-old-1"),
    ("BR", "So the rebels shut out one group and the establishment shut out another. Nobody in that fight walks away clean, my friends.", None),
    ("M", "That's the lesson of Rhode Island. Every side drew a line around who counted. They just drew it in different places.", None),
    # 7 what's left
    ("M", "In 1843 James Fenner became the first governor under the new constitution. He served until 1845. He died the next year, April 17th, 1846, at his Providence mansion, which he called What Cheer.", "card:Fact 7 of 7|Fenner was the first governor under Rhode Island's 1842 constitution"),
    ("M", "He is buried in the North Burial Ground in Providence, a short walk from College Hill.", "ri-northburial-1"),
    ("BR", "Three numbers on the list. Ever true. Thayer out.", None),
    ("M", "Three numbers for one man, and for most of his life, most of his neighbors never got one vote.", "ri-collegehill-1"),
    ("M", "Rhode Island. Keep it real.", "ri-brown-1"),
])

# ---------------------------------------------------------------- 3. New York
ep(3, "ny", "New York", "The Man Between the Clintons", [
    ["ny-yates", "Joseph C. Yates governor portrait"],
    ["ny-clinton", "DeWitt Clinton portrait"],
    ["ny-schenectady", "Stockade Historic District Schenectady"],
    ["ny-union", "Union College Schenectady Nott Memorial"],
    ["ny-albany", "Old New York State Capitol Albany 1820"],
    ["ny-canal", "Erie Canal 1825 painting"],
    ["ny-canal-lock", "Erie Canal lock Lockport"],
    ["ny-columbia", "Low Memorial Library Columbia"],
    ["ny-columbia-old", "Columbia College 1790 engraving"],
    ["ny-cornell", "Cornell University McGraw Tower"],
    ["ny-keuka", "Keuka Lake Penn Yan"],
    ["ny-yates-county", "Yates County Courthouse Penn Yan"],
    ["ny-seneca", "Seneca Lake vineyards"],
    ["ny-1821", "New York Constitution 1821 convention"],
    ["ny-cityhall", "New York City Hall 1825"],
], [
    ("CHAP", "", "card:Chapter Three · New York|Joseph C. Yates · Columbia and Cornell's state"),
    ("M", "Albany, New York. The fall of 1821. Delegates from across the state write a new constitution. And in one document they do two things at once.", "ny-albany-1"),
    ("M", "They throw open the polls to working white men by removing the property requirement. And for Black men, they keep a property requirement so steep that it shuts out nearly all of them.", "card:New York's constitution, 1821|Property test dropped for white men, kept for Black men"),
    ("CO", "Lions, good evening from Morningside Heights. And yes, one of the men arguing for Black suffrage at that convention was Peter Augustus Jay, a Columbia man. He lost.", None),
    ("G", "Wait. They opened the door and closed it in the same breath?", None),
    ("M", "Same breath, Gary. The voters ratified it in January 1822. And that November, those voters elected a new governor. Joseph C. Yates. Number seven.", "ny-yates-1"),
    # 2 origins
    ("M", "Joseph Christopher Yates was born in Schenectady on November 9th, 1768, and he died there in 1837. He is the only governor of New York born in Schenectady County.", "card:Fact 1 of 7|Born in Schenectady, 1768 · the only NY governor born in Schenectady County"),
    ("M", "He did not go to college. He read law with an established firm. In a state run by Columbia men and their friends, that made him something of an outsider.", "ny-schenectady-1"),
    ("CR", "Big Red, Ithaca is gorges tonight. And for the record, Cornell wouldn't exist for another forty-some years. Yates had no Ivy to skip.", None),
    # 3 climb
    ("M", "In 1798 he became mayor of Schenectady. He held the job through twelve one-year terms. And here's the thing. He was appointed to every one of them. Nobody voted him in.", "card:Fact 2 of 7|Mayor of Schenectady from 1798, appointed to twelve one-year terms"),
    ("M", "He helped found Union College in 1795, as one of its first trustees. He went to the state senate in 1805, and in 1808 he became a justice of the New York Supreme Court.", "ny-union-1"),
    ("G", "Twelve terms without one vote. I'd like that deal for my parking spot.", None),
    # 4 number seven
    ("M", "The count in New York is easy once you know the rule. The state lists each governor once, no matter how many times they served. George Clinton is number one. DeWitt Clinton, his nephew, is number six. Then Yates is seven.", "card:Fact 3 of 7|New York counts each governor once · Yates is No. 7"),
    ("M", "Count the comebacks separately, and the list shifts. George Clinton's return in 1801 pushes everybody down a slot, and DeWitt Clinton lands at seven instead of Yates.", "ny-clinton-1"),
    ("CO", "DeWitt Clinton was in the first class to graduate under the name Columbia College. If anyone deserves a recount, darling, it's him.", "ny-columbia-old-1"),
    # 5 big swing
    ("M", "Yates was sworn in on January 1st, 1823, for a two-year term. He is sandwiched between DeWitt Clinton's two runs as governor. Clinton came before him, and Clinton came right after him.", "card:Fact 4 of 7|Governor January 1, 1823 to December 31, 1824 · between DeWitt Clinton's two terms"),
    ("M", "These were the canal years. Clinton had sold the state on the Erie Canal, which critics called Clinton's Ditch. It ran from the Hudson to Lake Erie. It was dug with shovels, wheelbarrows and animal power, and many of the laborers were Irish immigrants.", "ny-canal-1"),
    ("M", "In April 1824, the Bucktail majority in the legislature, Yates's own side, voted to throw Clinton off the canal commission. The backlash was enormous. Clinton ran for governor that fall and won.", "ny-canal-lock-1"),
    ("G", "So the guy who replaced Clinton got replaced by Clinton.", None),
    ("CO", "New York, Gary. We recycle.", None),
    # 6 twist
    ("M", "And here's the twist. Joseph Yates is the governor history skips. One term, wedged between a famous man and a famous ditch. But skip him and you skip the electorate he governed, the one the 1821 deal built.", "ny-1821-1"),
    ("M", "Before 1821, property, not race, was the main test for voting in New York. After it, almost no Black men could vote. History calls the 1820s the age of the common man. In New York, the common man had to be white.", "card:Fact 5 of 7|The 1821 rules effectively disfranchised nearly all Black men in New York"),
    ("CR", "And the canal men? The ones who dug the thing? They don't get a county.", None),
    ("M", "They do not. But he did.", None),
    # 7 legacy
    ("M", "In February 1823 the legislature carved a new county out of Ontario County, in the Finger Lakes, and Governor Yates signed the law. They named it Yates County. There is also a Town of Yates.", "card:Fact 6 of 7|Yates County, formed 1823, is named for him · so is the Town of Yates"),
    ("M", "Before the land sales and treaties of the late 1700s, that country was Haudenosaunee land. The Seneca lived between the Genesee River and the lakes. Then the speculators surveyed it into lots.", "ny-keuka-1"),
    ("CR", "And from there it's a short drive east to Ithaca, where Cornell sits in Tompkins County. Named, of course, for another governor. Daniel Tompkins, number four.", "ny-cornell-1"),
    ("M", "John Vanderlyn painted his portrait, and the City of New York still owns it. His house still stands on Front Street, inside Schenectady's Stockade Historic District.", "card:Fact 7 of 7|His portrait by John Vanderlyn belongs to the City of New York"),
    ("CO", "Roar, Lion, roar. Goodnight.", None),
    ("M", "An open door, with a toll booth for some. Joseph C. Yates, New York's number seven.", "ny-schenectady-2"),
    ("M", "New York. Keep it real.", "ny-columbia-1"),
])

# ---------------------------------------------------------------- 4. Massachusetts
ep(4, "ma", "Massachusetts", "Five Tries and a Free State", [
    ["ma-sullivan", "James Sullivan governor Massachusetts Gilbert Stuart"],
    ["ma-gore", "Christopher Gore Trumbull portrait"],
    ["ma-gorehall", "Gore Hall Harvard"],
    ["ma-harvard", "Harvard Yard Massachusetts Hall"],
    ["ma-statehouse", "Old State House Boston"],
    ["ma-berwick", "South Berwick Maine"],
    ["ma-cushing", "William Cushing portrait"],
    ["ma-mumbett", "Elizabeth Freeman Mum Bett portrait"],
    ["ma-shays", "Shays Rebellion"],
    ["ma-granary", "Granary Burying Ground Boston"],
    ["ma-sullivansq", "Sullivan Square Charlestown"],
    ["ma-middlesex", "Middlesex Canal"],
    ["ma-hancock", "John Hancock portrait Copley"],
    ["ma-goreplace", "Gore Place Waltham"],
    ["ma-continental", "Continental currency"],
], [
    ("CHAP", "", "card:Chapter Four · Massachusetts|James Sullivan · Harvard's state"),
    ("M", "Worcester County, Massachusetts. 1781. A Black man named Quock Walker leaves the farm of the man who claims to own him. The man, Nathaniel Jennison, catches him and beats him.", "ma-statehouse-1"),
    ("M", "Walker sues. A jury declares him a free man. And the cases that follow help end slavery in Massachusetts, without a single law ever being passed to do it.", "card:The Quock Walker cases|Worcester County, 1781 to 1783"),
    ("HA", "Crimson, the floor is mine. And this is the part of Massachusetts history we should lead with, every time.", None),
    ("G", "I thought slavery was a Southern thing.", None),
    ("M", "It was a Massachusetts thing too, Gary. In the criminal case against Jennison, one of the judges at the preliminary hearing was the man who'd become our seventh governor. James Sullivan.", "ma-sullivan-1"),
    # 2 origins
    ("M", "James Sullivan was born April 22nd, 1744, in Berwick, in the part of Massachusetts that's now Maine. He never went to college.", "ma-berwick-1"),
    ("M", "As a boy he hurt his foot badly, and while he was laid up, he taught himself Latin and the classics at home. Then he studied law under his older brother, John.", "card:Fact 1 of 7|Self-taught at home after a childhood injury · no college"),
    ("HA", "No Harvard seat. And yet he outworked half the men who had one.", None),
    # 3 climb
    ("M", "In March 1776 he joined the Superior Court of Judicature, the colony's highest court, soon to be the state's. He resigned in 1782 in a fight over salary.", "card:Fact 2 of 7|A judge on the state's highest court, 1776 to 1782"),
    ("M", "He publicly opposed slavery. While Walker's lawyers, Levi Lincoln and Caleb Strong, argued the civil cases, the criminal case climbed to the top court. In April 1783, Chief Justice William Cushing told the jury that slavery was, in his judgment, as effectively abolished as it can be. Jennison was convicted and fined forty shillings.", "ma-cushing-1"),
    ("M", "By the 1790 census, Massachusetts reported no enslaved people at all.", "card:Fact 3 of 7|By the 1790 census, Massachusetts reported no enslaved people"),
    ("M", "In 1787, after Shays' Rebellion, the armed uprising in western Massachusetts, Sullivan helped defend men charged in it, and the government's lawyers criticized him for it.", "ma-shays-1"),
    ("M", "From 1790 to 1807 he served as attorney general of Massachusetts.", None),
    ("G", "So he's a judge, he's against slavery, he defends the rebels. When does he become governor?", None),
    # 4 number seven / 5 big swing
    ("M", "Not for a while. He ran for governor and lost in 1797. Lost in 1798. Lost in 1805. Lost in 1806. Four straight defeats.", "card:Fact 4 of 7|He lost four races for governor before he won in 1807"),
    ("M", "In 1807 he finally won. He's the seventh governor because Massachusetts gives a new number every time someone comes back. John Hancock served twice, so he is number one and number three.", "ma-hancock-1"),
    ("HA", "And if you count each man once, Hancock only takes one slot, and number seven becomes Christopher Gore. Hold that thought.", None),
    ("M", "Sullivan took office May 29th, 1807. He founded the Massachusetts Historical Society as its first president, and he was a major force behind the Middlesex Canal, which linked the Merrimack River to Boston.", "card:Fact 5 of 7|Founding president of the Massachusetts Historical Society · champion of the Middlesex Canal"),
    ("M", "But his time in the governor's chair was short. James Sullivan died in office on December 10th, 1808, after about eighteen months.", "ma-middlesex-1"),
    # 6 twist: Gore
    ("M", "Now, the man waiting at number eight. Christopher Gore. Harvard class of 1776. One of the richest lawyers in the country.", "ma-gore-1"),
    ("M", "Continental soldiers had often been paid in paper, and many of them sold it at a steep discount just to get by. Gore bought it. One batch cost him about thirty-seven hundred dollars for twenty-five thousand dollars face value.", "card:Fact 6 of 7|Gore bought soldiers' war paper at a steep discount"),
    ("M", "Then in 1790, Congress, on Alexander Hamilton's plan, made that paper good at face value. The soldiers had sold low. The buyer cashed in.", "ma-continental-1"),
    ("G", "So the guys who fought the war sold their pay for pennies, and the lawyer got rich off it.", None),
    ("HA", "That's the story, Gary. Harvard named its first library after him. Gore Hall, 1838.", "ma-gorehall-1"),
    ("M", "Gore lived grandly at his country estate, Gore Place in Waltham, now a National Historic Landmark. Sullivan took the long road. Four losses, one win, and a grave.", "ma-goreplace-1"),
    # 7 legacy
    ("M", "James Sullivan is buried in Boston's Granary Burying Ground, in a tomb he shares with a colonial governor, Richard Bellingham. Sullivan Square in Charlestown carries his name. And Harvard gave him an honorary degree in 1779.", "card:Fact 7 of 7|Sullivan Square is named for him · buried in the Granary Burying Ground"),
    ("HA", "Veritas. And the truth here is that the courts moved faster than the lawmakers did. Ashworth out.", "ma-granary-1"),
    ("M", "Four losses before a win. His side of history took a lot longer.", "ma-harvard-1"),
    ("M", "Massachusetts. Keep it real.", "ma-sullivansq-1"),
])

# ---------------------------------------------------------------- 5. New Hampshire
ep(5, "nh", "New Hampshire", "Who Owns a College", [
    ["nh-plumer", "William Plumer governor New Hampshire"],
    ["nh-dartmouth", "Dartmouth Hall Dartmouth College"],
    ["nh-green", "Dartmouth Green Hanover"],
    ["nh-webster", "Daniel Webster portrait"],
    ["nh-marshall", "John Marshall Chief Justice portrait"],
    ["nh-wheelock", "Eleazar Wheelock portrait"],
    ["nh-occom", "Samson Occom portrait"],
    ["nh-statehouse", "New Hampshire State House Concord"],
    ["nh-epping", "Epping New Hampshire"],
    ["nh-newburyport", "Newburyport Massachusetts historic"],
    ["nh-monroe", "James Monroe portrait"],
    ["nh-jqa", "John Quincy Adams portrait"],
    ["nh-charter", "Dartmouth College charter 1769"],
    ["nh-supreme", "Old Supreme Court Chamber Capitol"],
], [
    ("CHAP", "", "card:Chapter Five · New Hampshire|William Plumer · Dartmouth's state"),
    ("M", "Concord, New Hampshire. June 1816. A new governor takes office, and within weeks the state does something that sounds radical even now. It rewrites the charter of its elite private college and puts it under public control.", "nh-statehouse-1"),
    ("M", "Dartmouth College becomes, by law, Dartmouth University. State-appointed trustees. A state board of overseers. The new university moves into the college buildings in Hanover.", "nh-dartmouth-1"),
    ("DA", "Big Green, greetings from Hanover! And yes, for a while there were two Dartmouths in one little town.", None),
    ("G", "Two governors in Rhode Island, two Dartmouths in New Hampshire. You people really like doubles.", None),
    ("M", "The governor in that chair was New Hampshire's number seven. William Plumer.", "nh-plumer-1"),
    # 2 origins
    ("M", "William Plumer was born June 25th, 1759, in Newburyport, Massachusetts. His family moved to Epping, New Hampshire, in 1768, when he was eight or nine. He did not go to college.", "nh-newburyport-1"),
    ("M", "Before he was a lawyer, he was a Baptist lay preacher. Then he studied law and went into politics. He never sat in a college classroom. Later, he went after one.", "card:Fact 1 of 7|A Baptist lay preacher before he became a lawyer · no college"),
    ("DA", "A preacher, a lawyer, then a governor. Very North Country. You do whatever the season needs.", None),
    # 3 climb
    ("M", "He was Speaker of the New Hampshire House in 1791 and 1797. In 1802 he went to the United States Senate as a Federalist.", "card:Fact 2 of 7|Speaker of the New Hampshire House, 1791 and 1797"),
    ("M", "In 1803, when Jefferson bought Louisiana, some New England Federalists talked about leaving the Union. Plumer was one of them. Years later he called it the greatest political error of his life.", "card:Fact 3 of 7|He joined the 1803 secession talk, and later called it his greatest error"),
    ("G", "Okay, a guy who admits he was wrong. I like him already.", None),
    # 4 number seven
    ("M", "Now, the count. From 1784 to 1792 New Hampshire's chief executive was called President, not Governor. The standard list counts those presidents anyway. Meshech Weare, John Langdon, John Sullivan, Josiah Bartlett. Then John Taylor Gilman, Jeremiah Smith. And seven, Plumer.", "card:Fact 4 of 7|Counting the early presidents, Plumer is New Hampshire's 7th governor"),
    ("M", "New Hampshire gives each person just one number, so Plumer's two runs, 1812 to 1813 and 1816 to 1819, both count as seven. Count only from the 1792 title of governor, and seven becomes Levi Woodbury.", "nh-statehouse-2"),
    ("G", "And John Sullivan up there is the brother of the Massachusetts guy?", None),
    ("M", "Same family, Gary. James was Massachusetts number seven. His brother John was New Hampshire number three.", None),
    # 5 big swing: Dartmouth
    ("M", "So, Dartmouth. When Plumer came back in 1816, the college was in a feud between its president, John Wheelock, and its trustees. The state stepped in. The 1816 law reinstated Wheelock, added trustees, and gave the governor power over appointments.", "nh-wheelock-1"),
    ("M", "The college's old trustees sued the state-approved secretary of the new board, William H. Woodward. The case went to the United States Supreme Court. Daniel Webster, Dartmouth class of 1801, argued for the college.", "nh-webster-1"),
    ("M", "In 1819, Chief Justice John Marshall ruled for the college. A charter, he said, is a contract, and the Constitution forbids a state from breaking a contract. Dartmouth University disappeared.", "card:Fact 5 of 7|Dartmouth College v. Woodward, 1819 · the state lost"),
    ("DA", "Stay green. Though honestly, the state wanted the college to answer to the public. That's not a crazy idea.", None),
    # 6 twist
    ("M", "And here's the twist. That ruling reached far beyond Hanover. It told private corporations that their charters were contracts the states could not easily touch. States later learned to write in the right to change charters, but the case set the terms for generations.", "nh-supreme-1"),
    ("M", "And look at what the college was chartered to do. Dartmouth's 1769 charter names the education of youth of the Indian tribes as a purpose. A Mohegan minister, Samson Occom, raised more than twelve thousand pounds in Britain to fund that mission.", "nh-occom-1"),
    ("M", "Eleazar Wheelock used that money to found Dartmouth. And in its first two hundred years, nineteen Native American students graduated. It wasn't until 1970, under President John Kemeny, that Dartmouth officially recommitted to its founding mission.", "card:Fact 6 of 7|In Dartmouth's first 200 years, 19 Native American students graduated"),
    ("G", "Twelve thousand pounds raised by a Native preacher, and nineteen graduates in two hundred years.", None),
    ("M", "He lost. The trustees won. And the people the college was chartered to serve were mostly left outside.", None),
    # 7 legacy
    ("M", "In 1820, Plumer was a presidential elector. Every other elector in the country voted for James Monroe. Plumer alone voted for John Quincy Adams.", "nh-jqa-1"),
    ("M", "He became the first president of the New Hampshire Historical Society. He died on December 22nd, 1850, at ninety-one. At the time he was the oldest living former governor in the country, and the oldest governor America had ever had.", "card:Fact 7 of 7|The lone 1820 elector against Monroe · died at 91, the oldest governor ever"),
    ("DA", "The lone dissenter. A very New Hampshire thing to be. Hollis out.", "nh-epping-1"),
    ("M", "He lost. The trustees won. Ask who that ruling is still protecting.", "nh-green-1"),
    ("M", "New Hampshire. Keep it real.", "nh-dartmouth-2"),
])

# ---------------------------------------------------------------- 6. New Jersey
ep(6, "nj", "New Jersey", "Iron and Ivy", [
    ["nj-dickerson", "Mahlon Dickerson portrait"],
    ["nj-nassau", "Nassau Hall Princeton"],
    ["nj-nassau-old", "Nassau Hall 1764 engraving"],
    ["nj-maclean", "Maclean House Princeton"],
    ["nj-whiskey", "Whiskey Rebellion Washington reviewing troops Fort Cumberland"],
    ["nj-navy", "USS Constitution 1830s"],
    ["nj-jackson", "Andrew Jackson portrait"],
    ["nj-vanburen", "Martin Van Buren portrait"],
    ["nj-mine", "Dickerson Mine Succasunna"],
    ["nj-iron", "Morris County iron mine New Jersey history"],
    ["nj-reservation", "Mahlon Dickerson Reservation"],
    ["nj-trenton", "New Jersey State House Trenton"],
    ["nj-succasunna", "Succasunna New Jersey"],
    ["nj-philemon", "Philemon Dickerson"],
], [
    ("CHAP", "", "card:Chapter Six · New Jersey|Mahlon Dickerson · Princeton, class of 1789"),
    ("M", "Washington, 1834. A former governor of New Jersey arrives in the capital ready to sail for Russia. Andrew Jackson has named him minister to the court of the czar.", "nj-jackson-1"),
    ("M", "When he gets to town, he learns he's not going anywhere. He's been made Secretary of the Navy instead.", "card:Fact 1 of 7|Named minister to Russia, he arrived to find he'd been made Secretary of the Navy"),
    ("PR", "Tigers, the party's in Jadwin. And honestly? Showing up for one job and getting another. That's just networking.", None),
    ("G", "I showed up for a job interview once and they gave me a different job. It was worse.", None),
    ("M", "That's how power worked when you knew the right people. Meet Mahlon Dickerson. New Jersey's seventh governor.", "nj-dickerson-1"),
    # 2 origins
    ("M", "Mahlon Dickerson was born April 17th, 1770, at Hanover Neck, New Jersey. He graduated from the College of New Jersey in 1789. Today we call it Princeton.", "card:Fact 2 of 7|Princeton, then the College of New Jersey, class of 1789"),
    ("M", "Princeton has done its own homework on that era. Its Princeton and Slavery project found that the college's first nine presidents all enslaved people at some point in their lives, and that on at least one occasion, enslaved people were auctioned at the President's House.", "nj-maclean-1"),
    ("PR", "Stay striped. But that's a stripe the old catalogs left out. Good on the place for printing it now.", None),
    # 3 climb
    ("M", "In 1794 Dickerson rode as a private in the New Jersey militia cavalry, part of the army sent to put down the Whiskey Rebellion, a revolt over a federal tax on whiskey in western Pennsylvania.", "card:Fact 3 of 7|In 1794 he rode with the militia sent against the Whiskey Rebellion"),
    ("M", "Then he crossed into Pennsylvania government himself. He served as the state's Adjutant General, and in 1808, briefly, as its Attorney General.", "nj-whiskey-1"),
    ("G", "A New Jersey guy running Pennsylvania's army. That's like a Toledo guy coaching Bowling Green.", None),
    # 4 number seven
    ("M", "The count in New Jersey is the cleanest of all seven. The state counts each person once and traditionally numbered only elected governors. Acting governors who filled gaps, like John Lambert in 1802, are left off.", "nj-trenton-1"),
    ("M", "William Livingston, William Paterson, Richard Howell, Joseph Bloomfield, Aaron Ogden, William Pennington. And number seven, Mahlon Dickerson, sworn in October 26th, 1815.", "card:Fact 4 of 7|New Jersey counts elected governors once each · Dickerson is No. 7"),
    ("PR", "No recounts, no asterisks. Very Princeton. We like a tidy guest list.", None),
    # 5 big swing
    ("M", "He didn't stay long. In February 1817 he resigned the governorship to go to the United States Senate, where he served for sixteen years and chaired the committee on manufactures.", "card:Fact 5 of 7|He resigned as governor in 1817 to go to the U.S. Senate"),
    ("M", "Then came the Navy. He ran it from 1834 to 1838, and when Martin Van Buren took over, Van Buren kept him. He sat in Jackson's cabinet in the years when the federal government was driving Native nations out of the Southeast.", "nj-navy-1"),
    ("M", "In 1840 Van Buren made him a federal judge in New Jersey. He resigned the next year, and the judgeship went to his brother, Philemon.", "nj-philemon-1"),
    ("G", "He handed his judgeship to his brother?", None),
    ("PR", "Gary. It's called keeping it in the family. The Griswolds did it with a governorship.", None),
    # 6 twist: iron
    ("M", "But the real Dickerson fortune came out of the ground. From 1810 until he died, he ran mines and an ironworks in Morris County, in the hills around Succasunna.", "card:Fact 6 of 7|Iron mines and an ironworks in Morris County, 1810 to 1853"),
    ("M", "Iron mining in that era was hard, dangerous work. The records we found tell us a lot about Mahlon Dickerson, his offices, his elections, his honors. They don't tell us the names of the men who went down into his mines.", "nj-iron-1"),
    ("M", "That's who gets left out of these stories. Not the governor. The miners.", "nj-mine-1"),
    # 7 legacy
    ("M", "Mahlon Dickerson died in Succasunna on October 5th, 1853. Today the Mahlon Dickerson Reservation, more than three thousand acres of Morris County park land, carries his name.", "card:Fact 7 of 7|The 3,200-acre Mahlon Dickerson Reservation is named for him"),
    ("PR", "Van Doren out. And Gary, take a hike there sometime. Lovely trails.", "nj-reservation-1"),
    ("M", "His name is on three thousand two hundred acres. Somebody ought to find the names of the people who worked them.", "nj-succasunna-1"),
    ("M", "New Jersey. Keep it real.", "nj-nassau-1"),
])

# ---------------------------------------------------------------- 7. Pennsylvania
ep(7, "pa", "Pennsylvania", "The Schoolhouse and the Fire", [
    ["pa-wolf", "George Wolf governor Pennsylvania"],
    ["pa-easton", "Easton Pennsylvania Centre Square"],
    ["pa-getter", "Getter's Island Easton"],
    ["pa-harrisburg", "Pennsylvania State Capitol Harrisburg old"],
    ["pa-school", "one-room schoolhouse Pennsylvania"],
    ["pa-philly", "Philadelphia 1830s engraving"],
    ["pa-riot", "Philadelphia race riot 1834"],
    ["pa-purvis", "Robert Purvis portrait"],
    ["pa-franklin", "Benjamin Franklin Duplessis portrait"],
    ["pa-mifflin", "Thomas Mifflin portrait Copley"],
    ["pa-penn", "College Hall University of Pennsylvania"],
    ["pa-penn-old", "University of Pennsylvania 1780 Academy Philadelphia"],
    ["pa-ritner", "Joseph Ritner governor"],
    ["pa-lafayette", "Lafayette College Easton"],
    ["pa-wolfgate", "George Wolf memorial gateway Easton"],
], [
    ("CHAP", "", "card:Chapter Seven · Pennsylvania|George Wolf · Penn's state"),
    ("M", "Easton, Pennsylvania. 1833. A man named Charles Getter is to be hanged for murder. The crowd that comes to watch is enormous. Estimates run from fifteen to twenty thousand people.", "pa-easton-1"),
    ("M", "The execution is moved out of town to an island in the river. The first attempt fails. The second one doesn't. And the next year, the governor signs a law ending public executions in Pennsylvania.", "pa-getter-1"),
    ("PE", "Quakers, hear ye, from the Palestra! A grim start, friends, but a humane end.", None),
    ("G", "Twenty thousand people to watch a hanging? What was wrong with these people?", None),
    ("M", "Not enough schools, Gary. Which brings us to the governor. George Wolf. Pennsylvania's seventh.", "pa-wolf-1"),
    # 2 origins
    ("M", "George Wolf was born August 12th, 1777, in Allen Township, Northampton County, He studied at a local classical academy, read law, and was admitted to the bar in 1799.", "card:Fact 1 of 7|Born 1777 in Northampton County · admitted to the bar in 1799"),
    ("PE", "No Penn for Mister Wolf. A country academy and a stack of law books. Your humble servant approves.", None),
    # 3 climb
    ("M", "He went to the United States House in 1824, a protectionist and a Jackson man. In 1829 he beat Joseph Ritner for governor, and in 1832 he beat Ritner again.", "card:Fact 2 of 7|U.S. Congress 1824 to 1829 · elected governor in 1829 and 1832"),
    ("M", "He served on the board of Lafayette College in Easton from 1827 until he died. He would make schools the fight of his life.", "pa-lafayette-1"),
    # 4 number seven
    ("M", "Now the count. Before 1790 Pennsylvania didn't have a governor. It had a Supreme Executive Council, and that council had a president. Seven of them.", "pa-harrisburg-1"),
    ("M", "The sixth president was Benjamin Franklin. The seventh was Thomas Mifflin, a 1760 graduate of the College of Philadelphia, which is Penn. Mifflin then became the first governor under the 1790 constitution.", "pa-mifflin-1"),
    ("M", "Count from 1790, and it's Mifflin, McKean, Snyder, Findlay, Hiester, Shulze, and seven, George Wolf.", "card:Fact 3 of 7|Counting governors from 1790, George Wolf is Pennsylvania's 7th"),
    ("PE", "And Franklin was the very first president of the Academy and College of Philadelphia. Penn's own. Hear ye.", "pa-franklin-1"),
    ("M", "Franklin is the story in miniature. He enslaved at least seven people over his life and ran ads selling enslaved people in his newspaper. In his last years he was president of the Pennsylvania Abolition Society. Both of those are Franklin.", "card:Benjamin Franklin|Enslaver, then president of the Pennsylvania Abolition Society"),
    # 5 big swing
    ("M", "Back to Wolf. Governors before him had tried to build a statewide system of common schools, open to every child, not just families who could pay. They failed. Wolf pushed, and in 1834 Pennsylvania passed its free school law.", "pa-school-1"),
    ("M", "He's remembered as the father of Pennsylvania's public schools. Easton put up a memorial gateway in his honor in 1888.", "card:Fact 4 of 7|Remembered as the father of Pennsylvania's public-school system"),
    ("M", "And on April 10th, 1834, he signed the law that ended public executions. Charles Getter was the last.", "card:Fact 5 of 7|On April 10, 1834, he signed the law ending public executions"),
    ("G", "Okay. Schools and no more public hangings. That's a good year.", None),
    ("M", "It was a good spring, Gary. Then came August.", None),
    # 6 twist
    ("M", "August 12th, 1834. Philadelphia. A mob of several hundred white men, many of them Irish immigrants, attacks a carousel on South Street called the Flying Horses, a place where Black and white residents mixed. Then it moves into Moyamensing and goes after Black-owned homes and buildings.", "pa-philly-1"),
    ("M", "For three nights the mob attacks Black homes and churches. The African Presbyterian Church is targeted. The Wharton Street Church is destroyed. When it's over, forty-four buildings are gone and two people are dead.", "card:Fact 6 of 7|The 1834 Philadelphia race riot, while Wolf was governor · 44 buildings destroyed, 2 dead"),
    ("PE", "In the City of Brotherly Love, friends. The name was a promise, not a description.", None),
    ("M", "The school law was a promise to every child in Pennsylvania. That August, the city showed who it actually protected.", "pa-riot-1"),
    ("M", "And it got worse. Wolf lost in 1835 to Ritner when his own Democrats split. And in 1838 Pennsylvania wrote a new constitution that took the vote away from Black men. Robert Purvis led the protest, the Appeal of Forty Thousand Citizens Threatened with Disfranchisement. Black Pennsylvanians didn't get the vote back until 1870.", "pa-purvis-1"),
    # 7 legacy
    ("M", "Andrew Jackson made Wolf First Comptroller of the Treasury, and later he ran the customs house in Philadelphia. He died there on March 11th, 1840.", "card:Fact 7 of 7|Wolf Street in Philadelphia and Wolf Hall at Penn State are named for him"),
    ("M", "There's a Wolf Street in South Philadelphia, schools in his name in Bath and Bethlehem, and a Wolf Hall at Penn State. Not Penn. Penn State.", "pa-wolfgate-1"),
    ("PE", "A distinction we at Penn insist upon. Quill out.", "pa-penn-1"),
    ("M", "He opened the schoolhouse door. The rest of the state was still deciding who got through it.", "pa-school-2"),
    # film close
    ("M", "Seven states. Seven governors. Griswold, Fenner, Yates, Sullivan, Plumer, Dickerson, Wolf. Not one of them is famous. Every one of them made choices about who counted.", "card:Lucky Seven|Griswold · Fenner · Yates · Sullivan · Plumer · Dickerson · Wolf"),
    ("G", "Matthew, I came in knowing one governor from back east. Now I know seven, and I'm mad at about four of them.", None),
    ("M", "That's the right number to be mad at, Gary. The Ivy League trained the men who ran these states. The question is never just who led. It's who got a say, who got left out, and who paid for it.", "pa-penn-old-1"),
    ("M", "Lucky seven. Keep it mid. Keep it real.", "card:Lucky Seven|A Hardwood Bricks film"),
])

# ---------------------------------------------------------------- extra beats, each inserted before the line that starts with its marker
EXTRA = {
1: [("Three years later, Connecticut named", [
    ("M", "Before he ever sat in the governor's chair, Griswold sat on Connecticut's highest court, from 1807 to 1809. He was a presidential elector for the Federalist ticket of Charles Cotesworth Pinckney and Rufus King. Bench, ballot, and a seat at every table that mattered.", "ct-capitol-3"),
    ("M", "And there's one more thing on his record. In 1803, when Thomas Jefferson bought Louisiana, Griswold was one of the New England Federalists who talked about taking New England out of the Union. Their region was losing power to the South and the West, and they did not like it.", "card:1803|New England Federalists talk about leaving the Union"),
    ("G", "Wait. The governor who wouldn't send his militia to the war also wanted to leave the country?", None),
    ("YA", "Gary, a gentleman never leaves. He simply considers other clubs.", None),
    ("M", "Remember that one, because two of our seven governors were in that same secession conversation in 1803. You'll meet the other one in New Hampshire. He lived long enough to call it a mistake.", None),
    ("M", "At home, Griswold married Fanny Rogers, and they had ten children. His grandson, another Matthew Griswold, went to Congress from Pennsylvania in the 1890s. In this family, public office was the family business.", "ct-lyme-2"),
    ("YA", "Ten children. Good heavens. Think of the tuition.", None),
    ("G", "Think of the canes.", None),
  ]),
  ("Now back to the man with the tongs.", [
    ("M", "So who was Matthew Lyon, really, by 1798? A mill owner. A printer whose paper was called The Farmers' Library. And when another paper wouldn't run his writing, he started one called The Scourge of Aristocracy. The Federalists nicknamed him the Spitting Lyon. To his voters, he was one of them.", "ct-lyon-3"),
    ("G", "The Scourge of Aristocracy? Okay, now I get why they wanted him gone.", None),
  ]),
],
2: [("Then the arsenal. Then the collapse.", [
    ("M", "The numbers tell it. In the 1840s Rhode Island had about twenty-three thousand adult white men. Fewer than ten thousand of them could vote. The rest were shut out by a rule written for a colony of farmers, in a state that was filling up with mills.", "card:The vote in Rhode Island, early 1840s|About 23,000 adult white men · fewer than 10,000 could vote"),
    ("M", "In December 1841 the People's Constitution went to its own unofficial vote. Nearly fourteen thousand men voted yes. Fifty-two voted no. Then in March 1842, the voters who already had the vote rejected a compromise constitution, eight thousand six hundred eighty-nine to eight thousand thirteen.", "ri-dorr-reb-2"),
    ("M", "On April 18th, 1842, Dorr was elected governor, unopposed, with about sixty-three hundred votes. Two days later the charter government re-elected King with about forty-nine hundred. Dorr's men called their side the people. Dorr's critics called the charter government's harsh new law against them the Algerine Law.", "ri-king-1"),
    ("BR", "The Algerine Law. Named by its enemies, my friends, the way the best laws always are.", None),
    ("G", "So the guy with fewer votes stays governor, and the guy with more votes goes to prison.", None),
    ("BR", "Welcome to Rhode Island in 1842, Gary. Bring a raincoat.", None),
  ]),
  ("In 1843 James Fenner became the first governor", [
    ("M", "When the new constitution went to the voters in November 1842, it passed seven thousand and twenty-four to fifty-one. A separate question asked whether only white men should vote. The voters rejected it by about three to one.", "card:November 1842|The new constitution passes 7,024 to 51 · a whites-only vote is rejected about 3 to 1"),
    ("M", "Dorr was arrested in October 1843 and tried for treason against the state. He was convicted and refused to swear an oath of allegiance. In June 1845 the legislature passed an act that set him free.", "ri-dorr-2"),
    ("BR", "He refused to say the words. You can call that stubborn. I call it a thesis.", None),
    ("M", "Fenner, meanwhile, had married Sarah Whipple Jenckes back in 1792. They had four children. He was the son of a governor, the husband of a Providence family, and a Brown man. He never had to ask permission to vote in his life.", "ri-fenner-2"),
  ]),
],
3: [("And here's the twist. Joseph Yates is the governor", [
    ("M", "And DeWitt Clinton was never a man to lose quietly. He'd already run for president once, in 1812, and won eighty-nine electoral votes against James Madison. In 1802 he fought a duel and wounded his opponent, after calling him a liar, a scoundrel and a villain.", "ny-clinton-2"),
    ("M", "In 1817 he'd won the governorship in a special election with forty-three thousand votes. Tammany Hall printed ballots for another man, who got fourteen hundred. Clinton founded the New-York Historical Society. He knew how to build things, and he knew how to make enemies.", "card:DeWitt Clinton|Governor No. 6 · ran for president in 1812 · founded the New-York Historical Society"),
    ("CO", "And in 1825, back in office, he rode the canal boat Seneca Chief to Buffalo, then emptied two casks of Lake Erie water into New York Harbor. Theater, darling. Pure Broadway.", "ny-cityhall-1"),
    ("G", "So Yates is the guy who had to follow that act.", None),
    ("CR", "And precede it. Poor man got Clinton on both sides. Like a sandwich with too much mustard.", None),
    ("M", "And how did Yates win in 1822? He ran almost unopposed. He got a hundred twenty-eight thousand four hundred ninety-three votes, nearly ninety-eight percent. The new electorate gave him a landslide. Just not an electorate that included most Black New Yorkers.", "card:New York governor, 1822|Yates 128,493 · Southwick 2,910"),
  ]),
  ("John Vanderlyn painted his portrait", [
    ("M", "Yates married three times, to Ann Ellice, Maria Kane, and Elizabeth De Lancey, and had three daughters. He was president of the Schenectady Savings Bank. In 1828 he was a presidential elector.", "ny-yates-2"),
    ("M", "And then the strangest part. He died in Schenectady on March 19th, 1837, and was buried in a family cemetery. In 1889, the records say, his remains were moved to a family mausoleum in the Bronx. But that mausoleum shows no sign that he's in it.", "card:Where is Joseph Yates?|Moved to a Bronx mausoleum in 1889, the record says · no sign he is there"),
    ("G", "They lost the governor?", None),
    ("CR", "Gary, they lost him while he was alive. Losing him afterward is just consistent.", None),
  ]),
],
4: [("He publicly opposed slavery.", [
    ("M", "The Walker cases weren't alone. In August 1781, in Great Barrington, an enslaved woman named Bett and a man named Brom sued for their freedom under the new state constitution, which said all men are born free and equal. The jury freed them and awarded thirty shillings. She took the name Elizabeth Freeman.", "ma-mumbett-1"),
    ("HA", "Elizabeth Freeman. Remember the name, because she didn't wait for anybody to hand it to her.", None),
    ("M", "Quock Walker's own civil suit ended with a jury calling him a free man and awarding him fifty pounds. The constitution of 1780 was never amended to ban slavery outright. The courts and the people who sued did the work.", "card:Massachusetts, 1780 to 1783|No law ended slavery · lawsuits did"),
  ]),
  ("Now, the man waiting at number eight.", [
    ("M", "Sullivan's public life went beyond the courtroom. In 1796 he served as the American agent on the commission that fixed the border between Maine and New Brunswick at the St. Croix River. He wrote a history of the District of Maine in 1795, and a history of land titles in Massachusetts in 1801.", "card:James Sullivan, historian|The History of the District of Maine, 1795"),
    ("G", "A guy who lost four elections and still found time to write two history books. I can't finish a crossword.", None),
    ("HA", "Some of us lose elections, Gary. Some of us lose crosswords.", None),
  ]),
  ("Gore lived grandly at his country estate", [
    ("M", "Gore had been the first United States Attorney for Massachusetts, appointed in 1789. He spent years in London on a Jay Treaty commission. In 1807 he defended a young lawyer named Thomas Selfridge, who had shot a man named Charles Austin on a Boston street. The foreman of the jury was Paul Revere. It took about fifteen minutes to acquit.", "card:Commonwealth v. Selfridge, 1807|Gore for the defense · Paul Revere, foreman · acquitted"),
    ("M", "He served one year as governor, 1809 to 1810, then lost to Elbridge Gerry. He went to the U.S. Senate in 1813 and opposed the War of 1812. A young Daniel Webster studied law in his office. Gore Hall stood at Harvard until 1915, when it was torn down to make room for Widener Library.", "ma-gorehall-2"),
  ]),
],
5: [("And look at what the college was chartered to do.", [
    ("M", "The case is called Trustees of Dartmouth College versus Woodward. And Webster's argument is remembered for one line, recorded later: It is, sir, as I have said, a small college. And yet there are those who love it.", "card:Daniel Webster, 1818|\"It is, sir, a small college\" · as recalled by a listener years later"),
    ("DA", "We put that line on everything, Gary. Mugs. Sweaters. Probably a canoe.", None),
    ("G", "So the little college beat the whole state.", None),
    ("M", "The little college beat the whole state, and corporations everywhere got a shield. That's not a small thing, Gary. That's the kind of ruling bank lawyers and railroad lawyers would cite for the next century.", None),
  ]),
  ("Eleazar Wheelock used that money", [
    ("M", "Occom crossed to Britain with Nathaniel Whitaker in 1766. He preached across Britain from February 1766 to July 1767, raising money from congregations that came to see a Native minister in person. Wheelock had promised the money for a school for Native students.", "nh-occom-2"),
    ("M", "Dartmouth's royal charter came on December 13th, 1769, from New Hampshire's colonial governor, John Wentworth, in the name of King George the Third. The charter's purposes put the Indian tribes first. The student body didn't.", "nh-charter-1"),
    ("DA", "Hanover in the snow is beautiful. But the man who raised the money deserved a better school than the one he got.", None),
  ]),
  ("He became the first president of the New Hampshire Historical Society.", [
    ("M", "In that same 1820 vote, Plumer also declined to vote for the vice president, Daniel Tompkins. One elector, alone against the whole country, twice in one ballot.", "nh-monroe-1"),
    ("M", "His son, William Plumer Junior, went to Congress from 1819 to 1825. Plumer was elected to the American Antiquarian Society in 1815. He spent his old age writing, collecting, and keeping records of the men he'd served with.", "card:William Plumer, historian|First president of the New Hampshire Historical Society"),
    ("G", "Okay. Preacher, senator, secession guy, sorry about the secession, takes on a college, loses, votes alone, writes history till ninety-one. That's a full life.", None),
    ("DA", "That's New Hampshire, Gary. Live free and argue with everybody.", None),
  ]),
],
6: [("But the real Dickerson fortune came out of the ground.", [
    ("M", "His Senate career had one strange twist. On January 30th, 1829, Dickerson resigned his seat, and the legislature immediately elected him again, to fill a different vacancy left by another senator's resignation. Same man, same chamber, new seat.", "card:January 30, 1829|Dickerson resigns his Senate seat and is re-elected the same day to another"),
    ("G", "He quit and got rehired before lunch.", None),
    ("PR", "Gary, that's not quitting. That's a lateral move.", None),
    ("M", "He was elected to the American Philosophical Society in 1807, the club Benjamin Franklin founded. In 1833 he was admitted to the Society of the Cincinnati, the hereditary club of Revolutionary officers and their descendants. In 1844 he helped write New Jersey's new constitution.", "card:Mahlon Dickerson|American Philosophical Society, 1807 · Society of the Cincinnati, 1833"),
    ("PR", "Clubs, clubs, clubs. Now that's a resume I respect.", None),
    ("M", "And while he was gathering clubs, the Navy he ran was a hard place for the men at the bottom. Sailors could still be flogged. Congress didn't ban the lash on American ships until 1850. The men at the top of the Navy didn't feel it. The men at the bottom did.", "nj-navy-2"),
  ]),
],
7: [("Back to Wolf. Governors before him", [
    ("M", "Getter was hanged for the murder of a woman named Margaret Lawall. And the crowd that came to watch, up to twenty thousand people, was bigger than most towns in the state. Pennsylvania's leaders looked at that crowd and decided hanging had become a show. Wolf ended the show.", "pa-getter-2"),
    ("PE", "A state that turns a hanging into a holiday has a schooling problem. Mister Wolf saw the connection.", None),
  ]),
  ("For three nights the mob attacks", [
    ("M", "The mob grew to four or five hundred. Mayor John Swift gathered a posse of about three hundred. On the first night, eighteen men were arrested. By the end, about sixty. The committee that studied the damage put it at around four to six thousand dollars. Lucretia Mott, the Quaker abolitionist, wrote about it in her letters.", "card:Philadelphia, August 12 to 14, 1834|A mob of 400 to 500 · about 60 arrests"),
    ("G", "Sixty arrests for forty-four buildings and two people dead.", None),
    ("PE", "Philadelphia counted the windows, Gary. It was slower to count the people.", None),
  ]),
  ("Andrew Jackson made Wolf First Comptroller", [
    ("M", "Wolf married Mary Erb in 1798. They had eight sons and a daughter. As governor he pushed the legislature to build canals, and to raise taxes to pay the state's debts for them. Taxes are never popular.", "pa-harrisburg-2"),
    ("M", "Ritner won that 1835 race as an Anti-Mason, and the Democrats split between Wolf and Henry Muhlenberg. The man who built the schools lost his job to a divided party and a split vote.", "pa-ritner-1"),
  ]),
],
}


def apply_extras():
    for e in EPISODES:
        for marker, add in EXTRA.get(e["n"], []):
            i = next(k for k, (_, t, _) in enumerate(e["lines"]) if t.startswith(marker))
            e["lines"][i:i] = add


apply_extras()


def main():
    for e in EPISODES:
        d = ROOT / "docs" / f"lucky7-{e['n']}-{e['slug']}"; d.mkdir(parents=True, exist_ok=True)
        used = {sp for sp, _, _ in e["lines"]} - {"CHAP", "TITLE"}
        lines, last_pic, on_card = [], None, False
        for sp, t, v in e["lines"]:
            if v is None and on_card and last_pic:
                v = last_pic   # a fact card shows for its own line only; the talk after it goes back to a picture
            if v is not None:
                on_card = v.startswith("card:")
                last_pic = last_pic if on_card else v
            lines.append({"speaker": sp, "say": t, "caption": t, "visual": v})
        spec = {"title": f"Lucky Seven {e['n']} {e['state']}", "own_credit": "Pictures from Wikimedia Commons, credited above",
                "save_all_vo": True, "rev": 2, "voices": {k: v for k, v in VOICES.items() if k in used}, "lines": lines}
        json.dump(spec, open(d / "lines.json", "w"), indent=1, ensure_ascii=False)
        json.dump({"commons": e["queries"]}, open(d / "broll_queries.json", "w"), indent=1)
        words = sum(len(t.split()) for _, t, _ in e["lines"])
        print(d.name, len(lines), "lines", words, "words", f"~{words / 2.55 / 60 + 0.4:.1f} min")


if __name__ == "__main__":
    main()
