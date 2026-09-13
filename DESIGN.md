# Beehaviour: a local hive guardian

Hackathon project. Proof of concept of a hive surveillance box that works
without internet, without mobile coverage and without a cloud. Everything is
processed inside the device installed on the hive itself.

---

## 1. The problem

Beekeepers keep their apiaries out in the field, often with no mobile coverage.
They visit every one or two weeks. Between visits, serious things happen that go
unnoticed until it is too late:

- The colony swarms and half the bees are gone.
- The queen dies and the colony fades out within weeks.
- An Asian hornet sets up at the entrance and blockades the hive.
- Someone steals the hive, or an animal or the wind knocks it over.
- Spraying nearby kills hundreds of bees in one afternoon.

By the time the beekeeper arrives, it is usually too late.

## 2. The idea

A small box with a camera and a few sensors that lives on the hive, watches the
entrance around the clock, and learns what a normal day looks like *for that
hive*. When something departs from normal, it records it with a timestamp and a
photo. When the beekeeper reaches the apiary, they connect with their phone and
see at a glance what has happened since the last visit.

It never needs internet. All the intelligence is inside the box.

## 3. What it watches

### 3.1 A camera over the entrance

The camera is mounted about 30 cm above the landing board, looking down, so it
sees both the board and the entrance slot. From that image the system does three
things:

Hive activity. It counts how many bees are on the landing board at any
moment, and how many go in and out. From that it builds each day's activity
curve: quiet at dawn, busy at midday, nothing at night. Every hive has its own
curve.

Abnormal-activity alert. If on a day with good weather the activity at a
given hour is far below or far above the usual, it raises a flag. It does not
claim a cause; it says "something is going on here, come and look". That one
signal covers several very different problems at once:

| Situation | What it looks like at the entrance |
|---|---|
| Swarming (the colony splits and half leaves) | A burst of activity one midday, then half the traffic for days |
| Pesticide poisoning | A sharp drop in activity over a few hours |
| Bee-eaters hunting nearby | Bees stop leaving during good hours |
| Robbing (bees from other hives steal the honey) | Chaotic traffic, far heavier than normal |
| Weak or sick colony | Activity tapering off slowly over weeks |

Intruder alert. The system knows what a bee looks like. If something moving
shows up at the entrance that is clearly not a bee, especially if it is
considerably larger, it raises an alert and saves a photo. This catches the
Asian hornet (*Vespa velutina*), the European hornet, wasps, a mouse, a perched
bird, or a hand touching the hive. It does not identify the species, but the
beekeeper sees the photo and knows immediately.

### 3.2 Two temperature and humidity sensors

One inside the hive, in the brood area. One outside, in the shade.

A healthy colony holds the brood at 34-35 °C no matter what happens outside, in
winter and in summer. Comparing the two sensors says a lot:

| Situation | What it looks like |
|---|---|
| Healthy colony | Inside temperature steady while the outside one swings |
| Queenless or very weak colony | Inside temperature starts tracking the outside one |
| Swarming approaching | Inside temperature and humidity rise in the days before |
| Risk of mould and condensation in winter | High inside humidity over days at low temperature |

### 3.3 A motion sensor

Fixed to the hive body. It detects the hive being moved, tilted or knocked. It
covers:

- Hive theft.
- Tipping over from wind or an animal (wild boar, badger).
- Knocks or handling outside visit hours.

When it fires, the camera saves a photo of the moment.

## 4. What the beekeeper sees

On arriving at the apiary, the beekeeper connects their phone or laptop to the
box. During development this is done over a cable. Later the box itself creates
a local WiFi network, with no internet behind it, that the phone joins like any
other.

A simple screen opens with:

- The list of alerts since the last visit, with date, time and photo where there is one.
- An activity chart for the last few days.
- Temperature and humidity charts, inside and outside.
- The hive's current status.

## 5. What is out of scope for this proof of concept

Deliberately left out, for now:

- Identifying the intruder's exact species. It only reports "something that is not a bee".
- Counting dead bees at the entrance.
- Telling apart the colour of the pollen the bees carry.
- Frame inspection with a camera when the hive is opened.
- A text assistant recommending what the beekeeper should do.
- Physical buttons for logging inspections.
- Remote alerting over radio (LoRa). This is on the table as a next step: the box
  would keep working locally and only send short notifications.
- Advanced learning of the hive's pattern. For now, simple "outside the usual" rules.

## 6. How it is demonstrated at the hackathon

There is no real hive. The demo works like this:

- Camera: the system processes real top-down entrance footage. Bee counting and
  the activity curve are shown live. For the intruder alert, either footage with a
  hornet is used, or a dark object is placed on a real board in front of the camera.
- Temperature: a sensor is warmed by hand, or cooled, to trigger the weak-colony alert.
- Motion: the box is pushed or tilted to trigger the theft or tip-over alert.
- Screen: the history and the alerts are shown on the connected phone or laptop.

---

## 7. Materials

### Available hardware

- Arduino UNO Q (Qualcomm Dragonwing QRB2210, 4 GB RAM, 32 GB storage). WiFi and
  Bluetooth built in.
- Modulino Thermo ×2 (temperature and humidity).
- Modulino Movement (accelerometer and gyroscope).
- Modulino Buttons (unused in this PoC).
- An attachable camera.

### Dataset

Bee Detection and Direction Estimation Dataset
<https://data.mendeley.com/datasets/8gb9r2yhfc/6>

- Vilnius Gediminas Technical University (Lithuania). Version 6, August 2024.
  CC BY 4.0: free to use with attribution.
- Camera 30 cm above the landing board, 8 hives, summer 2023. Exactly the camera
  angle chosen for this project.
- It contains:
  - 7,200 images at 1920×1080 with the bees labelled.
  - Videos with roughly 17,000 already-annotated bee trajectories, about 7 minutes in total.
  - 400 images with each bee's head and stinger position (orientation).
  - 156 images with the landing-board corners marked.
  - Behaviour labels: foraging, defending, fanning, washboarding.
- It contains bees only. No wasps, no hornets. That is why intruder detection is
  framed as "something that is not a bee" rather than species identification.

### Reference videos

- *Bee happy*: top-down bee detection, tracking and counting. Reference for the
  result we are after and for the camera framing.
  <https://www.youtube.com/watch?v=e2AaZVANBX8>
- Entrance footage for demos and testing.
  <https://www.youtube.com/watch?v=bg7paGfvTHI>
- The BeeHiveCastle channel: a 24/7 live entrance camera, three-quarter view from
  above. A source of long, busy clips.
  <https://www.youtube.com/@BeeHiveCastle>

### Notes on camera framing

- Chosen: near top-down, about 30 cm above the landing board, as in the Mendeley dataset.
- Leave margin of board, and of air in front of the entrance, because a hornet hovers
  or perches right there.
- A pale, matte landing board makes detection much easier.
- A hood over the camera, to keep out direct sun and moving shadows.
- Rejected: a head-on view of the slot (bees occlude each other) and a wide shot of
  the whole hive (bees come out too small).

### Quick glossary

- Entrance (*piquera*): the slot the bees go in and out through.
- Landing board (*tabla de vuelo*): the ledge in front of the entrance where bees land.
- Swarming: the colony splits and half of it leaves with the old queen. A loss of
  bees and of the harvest.
- Queenless colony: a colony with no queen. With no new brood, it dies out in weeks.
- *Vespa velutina*: the Asian hornet, an invasive species that hunts bees at the
  entrance. Established in Catalonia and northern Spain.
- Bee-eater: a migratory bird that eats bees on the wing. It hunts at a distance
  and does not land at the entrance.
- Varroa: a parasitic mite of the honeybee, the leading cause of colony loss
  worldwide. Not detected directly by this PoC.
- Robbing: bees from other hives coming in to steal honey from a weak colony.
