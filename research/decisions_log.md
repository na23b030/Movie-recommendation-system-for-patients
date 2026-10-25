Research and Decisions Log
Date: 25 October 2026 (IST)
Recorded: 11:11 AM IST

## Initial Research Review — 11:11 AM IST

### 1. Fatigue during treatment
- Looked at: American Cancer Society — Getting Help for Fatigue.
- Found: Treatment-related fatigue can affect energy and everyday activities.
- Not found: A clinical rule saying patients should avoid movies over a specific length or with complex plots.
- Decision: Explore runtime and plot complexity as soft ranking factors only when fatigue or concentration difficulty is reported. 
### 2. Photosensitivity
- Looked at: Epilepsy Foundation — Photosensitivity and Ofcom — Broadcasting Code, Section 2.
- Found: Certain flashing images and patterns can trigger seizures in photosensitive people.
- Not found: A complete, authoritative list of movies confirmed free of relevant flashing content.
- Decision: Investigate a deterministic hard exclusion when a patient reports a photosensitive trigger and a title has a confirmed relevant warning. Keep unknown separate from no warning.
### 3. Movie information and content warnings
- Looked at: TMDB API documentation and BBFC film classifications.
- Found: TMDB offers movie metadata; BBFC entries can give title-specific content advice.
- Decision: Investigate TMDB for base metadata and BBFC for selected content tags. Document the source, uncertainty, and gaps of each annotation. No dataset has been finalized yet.
  
## Detailed Research Review — 11:55 AM IST

### 4. Pediatric patients and age suitability

Researched: Stanford Children's Health and Children's Wisconsin entertainment guidelines.

The hospital entertainment guidelines discuss restrictions on potentially frightening, violent, or distressing themes in children's entertainment activities.

Decision: Include age ratings, violence, frightening scenes, and sensitive themes in our movie features. Hospital entertainment guidelines are not movie-specific, so our filtering decisions will need separate justification.

Sources: Stanford Children's Health, Children's Wisconsin

### 5. Migraine and sensory sensitivities

Researched: NHS guidance on migraine and vertigo.

Migraine can involve sensitivity to light and sound, nausea, and dizziness. This made me consider movie characteristics beyond genre and runtime.

Decision: Explore sudden loud sounds, flashing scenes, and intense camera movement as additional features. The connection between these movie features and patient comfort is an inference, not a direct clinical recommendation.

Sources: [NHS – Migraine](https://www.nhs.uk/conditions/migraine/), [NHS – Vertigo](https://www.nhs.uk/conditions/vertigo/)

### 6. Emotional sensitivity

Researched: Hospital entertainment guidelines and BBFC content classifications.

BBFC records include information about violence, threat, and distressing themes. However, patients may respond differently to emotionally intense content.

Decision: Include content-warning tags and allow patients to specify themes they want to avoid. We should not automatically assume that patients undergoing treatment only want light-hearted movies.

Source: BBFC

### 7. Accessibility

Researched: W3C guidance on captions and audio descriptions.

Captions and audio descriptions make movies more accessible to people with hearing or visual difficulties. Availability may differ between platforms and movie versions.

Decision: Consider subtitle and audio-description availability as movie attributes, recording unknown values where reliable information is unavailable.

Source: W3C Web Accessibility Guidelines

## Final Research Review — 12:35 AM IST

### 8. Movie data sources and limitations

Looked at: TMDB, OMDb, Wikidata, MovieLens, and BBFC.

Found: Wikidata provides openly licensed structured movie information. MovieLens contains movie titles, genres, and user ratings, while BBFC provides more detailed content advice, including violence, threatening scenes, and flashing-content warnings.

Limitations: TMDB's terms restrict AI/ML applications, and MovieLens has restrictions on redistribution. BBFC does not provide every sensitivity attribute needed for the project.

Decision: Investigate Wikidata as the main metadata source and use BBFC records for verified content warnings where available. Check the source terms before collecting or redistributing data. Record the source and relevant movie version for each important annotation.

Sources:

Wikidata

MovieLens

TMDB Terms

BBFC

### 9. Dataset features and annotation strategy

Looked at: Available movie metadata, BBFC content classifications, and the patient sensitivities identified during earlier research.

Found: Genre, runtime, age ratings, and content warnings can support recommendation and filtering. However, features such as plot complexity, pacing, camera movement, and sudden loud sounds are not consistently available as structured data.

Decision: Prioritize basic movie information, age suitability, flashing warnings, violence, distressing themes, and runtime. Consider manually annotating plot complexity and pacing using consistent criteria.

Missing data: Keep uncertain sensitivity tags as unknown rather than assuming the content is safe. Record the tagging method, source, and confidence level. Features with insufficient evidence will not be used for hard safety decisions.

