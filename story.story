scene Cave {
  description: "You wake up in a dark cave with a exit in distance"
  choice "Leave" -> Cliff
}

scene Cliff {
  description: "You can see a vast forest covering entire horizon."
  choice "Jump" -> Forest
  choice "Walk" -> SnakePit
}

scene Forest {
  if returning -> {
      description: "You ended up returning to the same place"
      unset returning
    }
  else -> {
      description: "You fell down in a dense forest."
    }
  choice "Left" -> DeepForest
  choice "North" -> Lake
}

scene SnakePit {
  description: "You started walking and suddenly fell in a Snake Pit, There is no more of you" 
}

scene DeepForest {
  description: "You kept walking deeper and deeper into the jungle."
  set returning
  choice "Keep Walking" -> Forest
}

scene Lake {
  description: "You hear a woman singing across the lake and got curious"
}
