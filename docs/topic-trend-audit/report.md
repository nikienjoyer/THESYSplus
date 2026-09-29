# Topic Trend Analysis: read-only cluster review

Generated: **2026-09-27 10:08 UTC**. Approved theses: **52**.
Corpus SHA-256: `5ce7dbdec521f92c04ccbc880ddba1be9013d6b3a3516757dc8ed5b0190bf2a9`

This fingerprint covers each approved thesis's UUID, title, abstract, and stored keywords in the production query order. If any of those fields or the approved set changes, rerun the report before using its conclusions.

**No live algorithm, thesis record, database value, or embedding was changed.** All labels below are heuristic suggestions until a human checks every member. The existing emerging/saturated/underexplored badges describe relative group size.

## How to review

1. Compare the three detailed groupings below, prioritizing shared **research subject** over application platform or technology.
2. For each member, mark whether the proposed group name fits. Open the thesis link to read its full abstract and keywords; consult its PDF when the stored metadata is doubtful.
3. A specific group name is verified for this snapshot only if every member fits it. If one does not, record the mismatch instead of accepting the name. This review cannot verify future uploads or changed metadata.

The live comparison path is **Trend Analysis → cluster card → thesis detail**. The thesis links below assume the local frontend is running at `http://localhost:5173` and that the reviewer is signed in.

## Comparison method

All configurations use the production tokenizer, min/max document frequencies, unigrams/bigrams, `sublinear_tf=True`, K-Means `n_init=10`, and the existing naming rules. For each family and k=5–12, the audit fits seeds 42 and 0–10. Stability is the median pairwise adjusted Rand index (ARI) across those runs. Separation is the median cosine silhouette, calculated within that family's vector space. **Do not compare silhouette values across different families as though they share one geometry.**

The two alternative examples below are chosen within their own family by highest stability among results with no singleton groups, breaking ties with silhouette. This is a numerical shortlist, not a claim that their subjects or names are more accurate.

| Representation | k | Seed-42 group sizes | Singletons | Median ARI | Median cosine silhouette |
| --- | ---: | --- | ---: | ---: | ---: |
| Current combined title + abstract + stored keywords | 5 | 15, 12, 11, 7, 7 | 0 | 0.240 | 0.031 |
| Current combined title + abstract + stored keywords | 6 | 11, 11, 11, 8, 6, 5 | 0 | 0.280 | 0.033 |
| Current combined title + abstract + stored keywords | 7 | 10, 9, 8, 8, 8, 6, 3 | 0 | 0.306 | 0.039 |
| Current combined title + abstract + stored keywords | 8 | 9, 9, 7, 7, 6, 6, 5, 3 | 0 | 0.343 | 0.043 |
| Current combined title + abstract + stored keywords | 9 | 8, 8, 7, 7, 6, 6, 5, 3, 2 | 0 | 0.358 | 0.045 |
| Current combined title + abstract + stored keywords | 10 | 9, 8, 8, 6, 5, 4, 4, 3, 3, 2 | 0 | 0.377 | 0.049 |
| Current combined title + abstract + stored keywords | 11 | 8, 7, 6, 5, 5, 5, 4, 4, 3, 3, 2 | 0 | 0.392 | 0.052 |
| Current combined title + abstract + stored keywords | 12 | 8, 7, 6, 5, 5, 5, 4, 3, 3, 3, 2, 1 | 1 | 0.415 | 0.056 |
| Same vocabulary; L2-normalized title:abstract:keywords weights 2:1:2 | 5 | 19, 13, 8, 8, 4 | 0 | 0.344 | 0.060 |
| Same vocabulary; L2-normalized title:abstract:keywords weights 2:1:2 | 6 | 17, 9, 9, 8, 6, 3 | 0 | 0.353 | 0.063 |
| Same vocabulary; L2-normalized title:abstract:keywords weights 2:1:2 | 7 | 9, 9, 8, 8, 8, 6, 4 | 0 | 0.342 | 0.071 |
| Same vocabulary; L2-normalized title:abstract:keywords weights 2:1:2 | 8 | 10, 9, 7, 6, 6, 6, 5, 3 | 0 | 0.405 | 0.087 |
| Same vocabulary; L2-normalized title:abstract:keywords weights 2:1:2 | 9 | 11, 9, 6, 5, 5, 5, 4, 4, 3 | 0 | 0.427 | 0.101 |
| Same vocabulary; L2-normalized title:abstract:keywords weights 2:1:2 | 10 | 9, 7, 7, 5, 5, 4, 4, 4, 4, 3 | 0 | 0.413 | 0.112 |
| Same vocabulary; L2-normalized title:abstract:keywords weights 2:1:2 | 11 | 8, 8, 6, 6, 5, 4, 4, 3, 3, 3, 2 | 0 | 0.453 | 0.120 |
| Same vocabulary; L2-normalized title:abstract:keywords weights 2:1:2 | 12 | 8, 8, 7, 5, 5, 4, 4, 3, 3, 2, 2, 1 | 1 | 0.469 | 0.123 |
| 2:1:2 weights; web, web-based, website, mobile, app excluded | 5 | 21, 10, 10, 8, 3 | 0 | 0.296 | 0.063 |
| 2:1:2 weights; web, web-based, website, mobile, app excluded | 6 | 13, 12, 10, 7, 6, 4 | 0 | 0.251 | 0.068 |
| 2:1:2 weights; web, web-based, website, mobile, app excluded | 7 | 12, 10, 9, 6, 6, 5, 4 | 0 | 0.313 | 0.073 |
| 2:1:2 weights; web, web-based, website, mobile, app excluded | 8 | 10, 8, 7, 6, 6, 6, 5, 4 | 0 | 0.356 | 0.093 |
| 2:1:2 weights; web, web-based, website, mobile, app excluded | 9 | 8, 7, 7, 7, 6, 5, 4, 4, 4 | 0 | 0.375 | 0.102 |
| 2:1:2 weights; web, web-based, website, mobile, app excluded | 10 | 7, 7, 6, 6, 6, 5, 4, 4, 4, 3 | 0 | 0.456 | 0.112 |
| 2:1:2 weights; web, web-based, website, mobile, app excluded | 11 | 7, 6, 6, 5, 5, 4, 4, 4, 4, 4, 3 | 0 | 0.459 | 0.125 |
| 2:1:2 weights; web, web-based, website, mobile, app excluded | 12 | 6, 6, 6, 5, 4, 4, 4, 4, 4, 4, 3, 2 | 0 | 0.489 | 0.131 |

## Configurations selected for member review

- **Production baseline:** k=8; current live names and members.
- **Weighted fields:** k=11; 2:1:2 field weights.
- **Weighted, subject-oriented:** k=12; same weights with five generic platform terms removed.

## Preliminary stored-metadata observations

These are spot checks against stored titles and keywords. They are **not** completed source-PDF verification or approval of a configuration.

- The current nine-thesis **Internet of Things** group has four clear IoT projects. The weighted-fields candidate groups those four with the non-IoT THESYS+ repository; the weighted, subject-oriented candidate groups the four together.
- Those four IoT projects still have different **research subjects**: assistive mobility, irrigation/agriculture, and retail. A technically coherent IoT group is therefore not automatically a subject-coherent group.
- The weighted, subject-oriented candidate labels a four-thesis group **Aeroponics**, but only the indoor-farming thesis has that subject. The existing author-keyword fallback chose a real keyword from one member that does not describe the other three.
- Neither alternative is ready to replace production based on these numerical scores or spot checks. Complete the member review before selecting a change.

## Production baseline

### Internet of Things — 9 theses

**Cluster ID:** 2 · **Size badge:** EMERGING · **Leading TF-IDF terms:** water, analysis, irrigation, user, iot, smart

The name is an **unverified suggestion**. For each thesis, mark whether its research subject fits this group name. Check the source document if stored metadata looks wrong.

- **THESYS+: A Semantic-Based Thesis Retrieval and Topic Trend Analysis System for CCS Undergraduate Theses at Pampanga State University** ([open thesis](http://localhost:5173/repository/dfd4a0cd-482f-4ad4-bb67-a8d356655640); UUID `dfd4a0cd-482f-4ad4-bb67-a8d356655640`)
  - Stored keywords: none
  - Abstract evidence: Traditional academic repositories rely on keyword-based searches, making it difficult to detect semantic topic redundancies or track research trajectories over time. To address this, THESYS+ was developed as an intelligent thesis retrieval and topic trend analysis platform for the College of…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
  - **Source check:** No stored keywords; inspect the source if this affects the topic.
- **Thesix: Centralized Web-Based Capstone And Thesis Repository With Bert-Driven Semantic Similarity Algorithm** ([open thesis](http://localhost:5173/repository/667fe89e-c714-484f-aaaa-7e09b0557e6c); UUID `667fe89e-c714-484f-aaaa-7e09b0557e6c`)
  - Stored keywords: BERT, Capstone Repository, Semantic Similarity, Academic Innovation
  - Abstract evidence: The increasing volume of capstone and thesis projects in academic institutions necessitates a centralized and accessible repository to streamline management, accessibility, and visibility. Addressing this need, THESIX: Centralized Web -Based Capstone and Thesis Repository with BERT -Driven Semantic…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **EXTHEALTH: A BROWSER EXTENSION FOR HEALTH INFORMATION ON X USING NATURAL LANGUAGE PROCESSING (NLP)** ([open thesis](http://localhost:5173/repository/8069344d-5287-40de-8e51-176fb13b8d2a); UUID `8069344d-5287-40de-8e51-176fb13b8d2a`)
  - Stored keywords: Health Misinformation, Browser Extension, Fact-checking, X, Twitter, Social Media
  - Abstract evidence: Many social media users lack the time or motivation to fact-check health-related claims they encounter online, allowing health misinformation to spread widely on platforms such as X (formerly Twitter). This study presents eXtHealth, a browser extension that uses Natural Language Processing (NLP) to…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **#31B: A 117 Emergency Communication Platform For Abuse Report In A Mobile Application** ([open thesis](http://localhost:5173/repository/b34020a4-99ff-4087-a7f8-09b9690e4063); UUID `b34020a4-99ff-4087-a7f8-09b9690e4063`)
  - Stored keywords: Domestic Abuse, Complaint, Mobile Application, VAWC
  - Abstract evidence: The proposed study aims to establish an idea of a free communication platform for the victims of abuse, that is user-friendly, with much better assistance and immediate response, with the help and support from the local authorities and social services. It would also be a big help to promote…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **ANTABE: AN INTELLIGENT GUIDE STICK FOR VISUALLY IMPAIRED** ([open thesis](http://localhost:5173/repository/b05abf84-2643-4d03-888b-80fdb187152d); UUID `b05abf84-2643-4d03-888b-80fdb187152d`)
  - Stored keywords: Visual Impairment, Smart Cane, Assistive Technology, Iot
  - Abstract evidence: Antabe is an intelligent assistive guide stick designed to enhance spatial awareness, obstacle avoidance, and independent mobility for visually impaired individuals in Guagua, Pampanga. Powered by an Arduino microcontroller, the device integrates ultrasonic sensors for multi-directional obstacle…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **AQUAFLOW: AN ARDUINO-POWERED SMART IRRIGATION SYSTEM FOR GUMAIN DAM** ([open thesis](http://localhost:5173/repository/22f74b8e-7c13-4714-bab3-67e10140965d); UUID `22f74b8e-7c13-4714-bab3-67e10140965d`)
  - Stored keywords: Smart Irrigation System, Arduino Technology, Blynk Application, IoT (Internet of Things), Water Flow Control, Water Level Monitoring
  - Abstract evidence: AquaFlow is an IoT-based automated irrigation system developed for agricultural fields connected to Gumain Dam in Floridablanca, Pampanga to reduce water wastage and prevent crop damage from overwatering or drought stress. Built through Rapid Application Development (RAD), the system integrates a…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **ShopEase: AN IOT-BASED SHOPPING CART WITH BARCODE SCANNER AND REAL-TIME MULTI-CART MONITORING SYSTEM** ([open thesis](http://localhost:5173/repository/3ee906b3-2e8d-4da9-b155-5a70c69ba4fa); UUID `3ee906b3-2e8d-4da9-b155-5a70c69ba4fa`)
  - Stored keywords: IoT (Internet of Things), Real-Time Monitoring, Multiple Carts, Cashier Application
  - Abstract evidence: Traditional supermarket checkout methods create significant friction for customers, often resulting in long queues and reduced operational efficiency. To resolve these challenges, this study developed ShopEase: An IoT-Based Shopping Cart with Barcode Scann er and Real-Time Multi-Cart Monitoring…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **Attachmates: A Dating App For Ai-Powered Compatibility-Based Matching Through Attachments Styles And Love Languages** ([open thesis](http://localhost:5173/repository/c1b8c2f6-69c3-47f6-80cb-ecaa3fb79c1c); UUID `c1b8c2f6-69c3-47f6-80cb-ecaa3fb79c1c`)
  - Stored keywords: attachment styles, love languages, dating fatigue, hybrid recommendation system, psychology-based matching, Flutter, Firebase, AI matching
  - Abstract evidence: Many dating applications today prioritize physical appearance and fast interactions, often leading to emotional mismatches, inconsistent connections, and dating fatigue among users. This study focused on development of AttachMates, a dating application designed to improve compatibility by…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **AnImo: An AI-Driven Agricultural Hybrid Platform with Intelligent Crop Recommendations and IoT-Enabled Solar-Powered Water Irrigation Based on Soil Analysis** ([open thesis](http://localhost:5173/repository/b1f3b63d-16ce-4458-8224-163564b61a8a); UUID `b1f3b63d-16ce-4458-8224-163564b61a8a`)
  - Stored keywords: Gemini, Internet of Things, Smart Farming, Solar -Powered Water Pump, Soil Analysis
  - Abstract evidence: Local farmers in the Philippines face significant challenges, including fluctuating market prices, soil degradation, and climate variability, which contribute to low productivity and economic losses. Addressing the urgent need for innovative technological solutions, this project developed AnImo: An…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______

### Data Analytics — 9 theses

**Cluster ID:** 1 · **Size badge:** EMERGING · **Leading TF-IDF terms:** performance, analytics, functional, web-based, management, data analytics

The name is an **unverified suggestion**. For each thesis, mark whether its research subject fits this group name. Check the source document if stored metadata looks wrong.

- **Hubisko: Scholarship Management In Pampanga Through Centralized Automation** ([open thesis](http://localhost:5173/repository/4d01b7a0-e453-43de-b900-8b84c41d6f70); UUID `4d01b7a0-e453-43de-b900-8b84c41d6f70`)
  - Stored keywords: Web Based Automation System, Scholarship
  - Abstract evidence: Scholarship application and management in the Philippines, particularly within Pampanga, remains largely dependent on manual and paper-based processes, creating inefficiencies for both student applicants and scholarship providers and making it difficult to keep scholarship-related information…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **APPOKO: A Web-Based Elderly Medication Monitoring System with Descriptive Analytics and GPS Tracking** ([open thesis](http://localhost:5173/repository/8fbe4f92-7420-477e-a16d-084927644b9c); UUID `8fbe4f92-7420-477e-a16d-084927644b9c`)
  - Stored keywords: Elderly healthcare management, web-based system, GPS tracking, Agile Software Development Methodology, Web-based Approach
  - Abstract evidence: The elderly care facility at Bahay Pag-ibig in Telabastagan, San Fernando, Pampanga, struggled to monitor residents and track medication due to a high resident-to-staff ratio, leaving administrators and caregivers unable to maintain healthcare management effectively with the limited workforce…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **ALUMNI PORTAL TRACKER WITH DATA ANALYTICS USING FOLD-GROWTH ALGORITHM** ([open thesis](http://localhost:5173/repository/ab97a031-f6b2-44e6-9a7e-6abcab04c809); UUID `ab97a031-f6b2-44e6-9a7e-6abcab04c809`)
  - Stored keywords: alumni portal, tracker, data analytics, fold-growth, algorithm, web based
  - Abstract evidence: Alumni Portal Tracker with Data Analytics using Fold-Growth Algorithm is a web-based Alumni Portal Tracker that enables the Don Honorio Ventura State University College of Computing Studies department in keeping and managing alumni records. It will serve as a useful interface for alumni and the d…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **TASKGROVE: A TREE-BASED PROJECT MANAGEMENT APPLICATION** ([open thesis](http://localhost:5173/repository/fd8a1ca0-665f-442b-b919-7afe31cdbbc5); UUID `fd8a1ca0-665f-442b-b919-7afe31cdbbc5`)
  - Stored keywords: project management, tree-based, task management, monitoring
  - Abstract evidence: TaskGrove is an online platform that is essential in today's project management landscape. Its emergence has brought about a significant revolution in the way tasks are organized within project frameworks, leading to a remarkable increase in productivity levels. This innovative platform not only…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **Web-Based Grading System With Data Analytics For The Modernized Processing Of President’s And Dean’s Lists Candidates** ([open thesis](http://localhost:5173/repository/a634c87e-abe4-486c-b9d7-29f6fa9585a8); UUID `a634c87e-abe4-486c-b9d7-29f6fa9585a8`)
  - Stored keywords: web-based system, data analytics, manual processing, grade verification, Optical Character Recognition (OCR)
  - Abstract evidence: This study addresses the inefficiencies of the manual processing of President’s List (PL) and Dean’s List (DL) applications at Pampanga State University, which is time-consuming and prone to delays. A web-based system was developed to streamline registration, grade computation, verification,…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **My Honorian Buddy: A Web-Based Peer-Tutoring System For The Students Of Pampanga State University** ([open thesis](http://localhost:5173/repository/2784252f-6995-4ce5-be72-87dd0d1276f1); UUID `2784252f-6995-4ce5-be72-87dd0d1276f1`)
  - Stored keywords: peer-tutoring, web-based, content-based algorithm
  - Abstract evidence: The increasing integration of technology in education has amplified the need for personalized academic support, particularly in online learning environments. My Honorian Buddy is a web-based peer-tutoring system that connects students one-onone with suitable peer tutors using a content -based…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **Headlink: An Iot-Powered Head Pose Tracking System For Assistive Input And Human-Computer Interaction** ([open thesis](http://localhost:5173/repository/1bb71d5b-494c-452b-89e3-28ecafd4a81a); UUID `1bb71d5b-494c-452b-89e3-28ecafd4a81a`)
  - Stored keywords: Head Pose Tracking, Assistive Technologies, Human-Computer Interaction, Gesture-Based Inputs, Raspberry Pi, IoT System
  - Abstract evidence: HeadLink is an IoT-Powered Head Pose tracking system designed to make computers more accessible by providing a hands-free alternative for human-computer interaction. It uses computer vision and facial landmarking to track head position and translate it into mouse movements and functions. HeadLink…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **DormHonorio: DORMITORY BOOKING AND ALGORITHM-DRIVEN ROOMMATE MATCHING MOBILE APPLICATION FOR HONORIANS** ([open thesis](http://localhost:5173/repository/7aa5c31d-8be0-4e1b-b4aa-1b6a87bb016c); UUID `7aa5c31d-8be0-4e1b-b4aa-1b6a87bb016c`)
  - Stored keywords: weighted scoring algorithm, roommate matching, dormitory, tenant
  - Abstract evidence: The goal of this study was to develop DormHonorio, a mobile application that helps Pampanga State University students find dormitories and compatible roommates in a more organized and reliable way. Since there is still no official online platform for this purpose, students often experience a…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **Development of Complaints and Grievances Management System Aligned with R.A. No. 11313** ([open thesis](http://localhost:5173/repository/2c902b58-ba62-4198-b663-fc72afbec25c); UUID `2c902b58-ba62-4198-b663-fc72afbec25c`)
  - Stored keywords: Case Management, Republic Act No. 11313, Safe Spaces Act, Web-Based System, Grievance Management, Gender-Based Sexual Harassment, ISO/IEC 25010
  - Abstract evidence: This study addresses the ongoing problems within Pampanga State University, particularly in the College of Computing Studies, which manages the complaint filing, delayed process, privacy violation, and unsettled cases for taking legal actions. To resolve these issues, the researchers developed a…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______

### Mobile Applications (Cluster 5) — 7 theses

**Cluster ID:** 5 · **Size badge:** EMERGING · **Leading TF-IDF terms:** farmers, agriculture, supply, learning, mobile, market

The name is an **unverified suggestion**. For each thesis, mark whether its research subject fits this group name. Check the source document if stored metadata looks wrong.

- **ARADA: AN ANDROID ONLINE MARKET WITH SUPPLY- DEMAND STATISTICS FOR SELECTED LOCAL FARMERS AND SUPPLIERS IN PAMPANGA** ([open thesis](http://localhost:5173/repository/9ae051ee-b6b5-4df2-9d03-876f594045f9); UUID `9ae051ee-b6b5-4df2-9d03-876f594045f9`)
  - Stored keywords: Farmer‟s Market, Supply -Demand Statistics, Public Market, Android Application, CoVid-19
  - Abstract evidence: Agriculture is vital to the Philippines' economy where it is among the nation’s major industries. On the other hand, Pampanga is a province where one of its main industries is agriculture. Most farmers’ selling locations are in local markets. However, due to Covid-19, travel restrictions were…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **MEMOLOOP: A CUSTOMIZABLE DIGITAL LEARNING FLASHCARDS FOR MEMORIZATION ASSESSMENT** ([open thesis](http://localhost:5173/repository/2724801d-2dfe-43a7-a941-5d633374baa0); UUID `2724801d-2dfe-43a7-a941-5d633374baa0`)
  - Stored keywords: Digital Flashcards, MemoLoop mobile application, Learning and Memorizing Information
  - Abstract evidence: MemoLoop is an Android mobile digital flashcard application engineered to enhance active recall and long-term memory retention for Bachelor of Science in Biology students at DHVSU. Developed using Flutter, Dart, Laravel, and MySQL, the application implements the SuperMemo SM-2 spaced repetition…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **A FUZZY LOGIC-BASED MOBILE APPLICATION FOR REAL-TIME MONITORING OF MODULAR INDOOR FARMING** ([open thesis](http://localhost:5173/repository/8212ab33-5c0e-4b1f-8383-583f1db45722); UUID `8212ab33-5c0e-4b1f-8383-583f1db45722`)
  - Stored keywords: Aeroponics, fuzzy logic algorithm, indoor
  - Abstract evidence: An automated indoor aeroponics system and mobile application developed to monitor and manage crucial plant environmental parameters, including temperature, humidity, pH, and water levels. Developed using a Waterfall model for the mobile app and a prototype model for the tower hardware, the system…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **PALE-NGKIHAN: ONLINE MARKET SYSTEM FOR ARAYAT RICE TRADERS** ([open thesis](http://localhost:5173/repository/9ade9f3c-ffde-4481-be98-b2605cc3abf1); UUID `9ade9f3c-ffde-4481-be98-b2605cc3abf1`)
  - Stored keywords: online market system, web-based, agricultural, rice trading, middlemen
  - Abstract evidence: A web-based e-commerce platform designed to establish a direct trading channel between rice farmers and buyers in Arayat, Pampanga. Developed using Agile methodology, the system eliminates price disparities caused by intermediaries by providing transparent pricing, product cataloging, order…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **ANIDELIVERY: A FARMERS PLATFORM FOR SUSTAINABLE AGRICULTURE THROUGH MACHINE LEARNING-POWERED DIGITAL MARKETPLACE IN PAMPANGA** ([open thesis](http://localhost:5173/repository/143fb188-2e1a-41f9-8400-ca42466fd8a3); UUID `143fb188-2e1a-41f9-8400-ca42466fd8a3`)
  - Stored keywords: AniDelivery, Digital Marketplace, Supply Chain Management, Over Supply, Under Supply, Consumer
  - Abstract evidence: A mobile and web-based digital marketplace created to support sustainable agriculture in Pampanga by facilitating direct transactions between farmers and consumers. Developed using an Agile Scrum methodology, the platform incorporates machine learning algorithms for sales forecasting to mitigate…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **CODEQUEST: WHEN JAVA PROGRAMMING MEETS PLAYFUL LEARNING** ([open thesis](http://localhost:5173/repository/3970223e-18b9-45df-88a2-99a83abdee02); UUID `3970223e-18b9-45df-88a2-99a83abdee02`)
  - Stored keywords: Gamification, Blended, Engagement, Effectiveness
  - Abstract evidence: CodeQuest is an interactive, web-based 3D gamified educational platform developed to enhance Java programming instruction through a blended learning approach. Developed using React.js, Three.js, Node.js, and PostgreSQL under the Agile Scrum framework, the system integrates quest-based programming…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **iSecure: An Integrated Web-Based System for Base Access and Security Operations** ([open thesis](http://localhost:5173/repository/a23823a2-bda9-4a96-9ed4-085d0a24b6e7); UUID `a23823a2-bda9-4a96-9ed4-085d0a24b6e7`)
  - Stored keywords: iSecure, Access Control, RFID, Facial Recognition, OCR, Security Operations, ISO/IEC 25010, Agile Scrum
  - Abstract evidence: In areas that needs high security people often use outdated paper-based systems to track and archive record. This can, in turn, run into problems due to human error and inefficiencies. The goal of this project was to develop a web-based system named iSecure that automates security procedures in…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______

### Geofencing Technology — 7 theses

**Cluster ID:** 4 · **Size badge:** EMERGING · **Leading TF-IDF terms:** geofencing, cashless, main campus, campus, main, geofencing technology

The name is an **unverified suggestion**. For each thesis, mark whether its research subject fits this group name. Check the source document if stored metadata looks wrong.

- **Sabiyahe: A Cashless Mobile-Based E-Jeepney Tracking And Seat Reservation System** ([open thesis](http://localhost:5173/repository/6486a500-ce43-45fb-9d9f-2e539fc86d41); UUID `6486a500-ce43-45fb-9d9f-2e539fc86d41`)
  - Stored keywords: E-Jeepney Tracking System, Seat Reservation, Cashless Payment
  - Abstract evidence: SaBiyahe: A mobile-based application is a system created for public commuting. Aims at easing the problem that is still occurring with the manual onboarding system of public utility jeepneys and vehicles (PUJ, PUV). With the use of the said system application commuters may engage boarding and E…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **Vehicle Management System using Cloud Mapping Technology** ([open thesis](http://localhost:5173/repository/ad4f3076-3c4e-4f73-b54a-2b6f97c485e4); UUID `ad4f3076-3c4e-4f73-b54a-2b6f97c485e4`)
  - Stored keywords: cloud server, mapping
  - Abstract evidence: Due to pandemic, limited transportation led to decrease in overall economic status of a country. In the Philippines, where most of the transactions were traditional, the said transportation industries had to adapt to the current situation. Through the help of the internet and newest web…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **Web-Based Qualifying Examination for Accountancy Students of Don Honorio Ventura State University – Main Campus** ([open thesis](http://localhost:5173/repository/11fdc7b9-4308-4e65-ac11-b57be86f8550); UUID `11fdc7b9-4308-4e65-ac11-b57be86f8550`)
  - Stored keywords: paper-based examination, web-based qualifying examination, digitized, database, data records, user-friendly, graphic user interface
  - Abstract evidence: Designed for the College of Business Studies at DHVSU Main Campus, this web-based examination platform digitizes the annual qualifying assessment for Bachelor of Science in Accountancy students. Developed using ASP.NET, SQL Server, and an Agile framework, the system replaces paper-based…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **COMPAWNION: A PROFILE MANAGEMENT SYSTEM with GEO-LOCATION SYSTEM for NOAH'S ARK DOG AND CAT SHELTER, MABALACAT, PAMPANGA** ([open thesis](http://localhost:5173/repository/f92512f4-5976-4844-bc95-fcbb77f47f7b); UUID `f92512f4-5976-4844-bc95-fcbb77f47f7b`)
  - Stored keywords: Geo-location, Profile Management, Stray pets, Dogs, Cats, Mabalacat City
  - Abstract evidence: Compawnion is a web-based animal profile and rescue management platform created for Noah's Ark Dog and Cat Shelter in Mabalacat City, Pampanga. Developed through an iterative software lifecycle, the system digitalizes sheltered pet records, coordinates adoption applications and donations, tracks…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **DORMIFY: DORM FINDER AND MANAGEMENT SYSTEM WITH GEOFENCING TECHNOLOGY FOR DHVSU MAIN CAMPUS** ([open thesis](http://localhost:5173/repository/827a721c-0ecc-4896-b9b4-f5571f32736c); UUID `827a721c-0ecc-4896-b9b4-f5571f32736c`)
  - Stored keywords: Dorm Finder, Management System, Geofencing Technology
  - Abstract evidence: Dormify is an Android-based dormitory finder and rental management system created for students, faculty, and property owners within a 1-kilometer radius of DHVSU Main Campus in Bacolor, Pampanga. Developed using an iterative model, the application incorporates Google Maps geofencing to display…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **HTEFinder: A Web Application Utilizing Geofencing Technology** ([open thesis](http://localhost:5173/repository/ca211b67-2032-48e0-90d8-d30c250a7804); UUID `ca211b67-2032-48e0-90d8-d30c250a7804`)
  - Stored keywords: On-the-Job Training, Host Training Establishment, Geofencing Technology, Expert System, Laravel Framework, MySQL Database
  - Abstract evidence: HTEFinder is a web-based platform developed to streamline the search and placement process of Host Training Establishments (HTE) for on-the-job training (OJT) students in the College of Computing Studies at DHVSU. Developed with the Laravel framework and MySQL using an iterative approach, the…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **DHVCHAT: A WEB-BASED INTELLIGENT CHAT ASSISTANT FOR THE ADMISSIONS OFFICE USING NATURAL LANGUAGE PROCESSING** ([open thesis](http://localhost:5173/repository/18737b6e-983a-4ae6-915a-8f155aefb160); UUID `18737b6e-983a-4ae6-915a-8f155aefb160`)
  - Stored keywords: Natural Language Processing, chatbots, university admission, AI-enhanced communication systems
  - Abstract evidence: DHVChat is an AI-powered conversational web assistant created for the Admissions Office of Don Honorio Ventura State University to automate student inquiry handling. Built using ReactJS, Python, and OpenAI's GPT-3.5 Turbo text embeddings within an iterative waterfall methodology, the system…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______

### Educational Technology — 6 theses

**Cluster ID:** 8 · **Size badge:** EMERGING · **Leading TF-IDF terms:** game, educational, educational game, interactive, learning, unity

The name is an **unverified suggestion**. For each thesis, mark whether its research subject fits this group name. Check the source document if stored metadata looks wrong.

- **KlasikoPinas: Filipino Traditions and Mythical Creatures Digital Game** ([open thesis](http://localhost:5173/repository/fc64acbe-4a43-4d27-bb0f-76fb7e279caf); UUID `fc64acbe-4a43-4d27-bb0f-76fb7e279caf`)
  - Stored keywords: Filipino traditions, traditional games, mythical creatures, digital game, Godot engine, KlasikoPinas
  - Abstract evidence: A 2.5D educational game developed using the Godot Engine and Blender to preserve Filipino cultural identity by teaching traditional outdoor games and indigenous folklore. Built using an Agile Kanban workflow, the game translates traditional games like Palosebo, Sipa, Luksong Baka, and Langit Lupa…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **Mamalakaya: A Web-based HIV Awareness Campaign Site with an Educational Game and Testing Centers Directory** ([open thesis](http://localhost:5173/repository/d9078b46-77bb-425c-a996-524ae65b9f72); UUID `d9078b46-77bb-425c-a996-524ae65b9f72`)
  - Stored keywords: HIV, educational game, awareness, education, campaign
  - Abstract evidence: An automated public health campaign website designed to provide accessible HIV education, destigmatization resources, and healthcare linkage during the COVID-19 pandemic. Developed using Agile methodology, the platform provides multimedia instructional content, an interactive educational game, a…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **MODEYUL: An Educational Kapampangan Supplemental Game App for Grade 3 Students** ([open thesis](http://localhost:5173/repository/f765b44b-073e-42d0-b453-f975d592d3dd); UUID `f765b44b-073e-42d0-b453-f975d592d3dd`)
  - Stored keywords: Programming, Unity Software, C#, 2D, Game App
  - Abstract evidence: Developed during the COVID-19 pandemic, ModeYul is an offline, module-based 2D educational Android game application designed to help Grade 3 students learn the Kapampangan language and local culture. Built using the Waterfall methodology with Unity and C#, the system incorporates interactive…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **CYBERESCAPE: A MOBILE EDUCATIONAL ESCAPE ROOM APPLICATION FOR NETWORKING FUNDAMENTALS** ([open thesis](http://localhost:5173/repository/8a1b73df-d71c-4458-82c9-b9721f655b94); UUID `8a1b73df-d71c-4458-82c9-b9721f655b94`)
  - Stored keywords: CyberEscape mobile game application, Educational mobile game, Digital Educational Escape Room, Gamified Learning
  - Abstract evidence: CyberEscape is an educational 2D mobile escape room game developed to improve comprehension of networking fundamentals among TVL-ICT Senior High School students at Tomas Dizon Foundation Institute. Built using Unity, C#, Aseprite, and the Octalysis gamification framework under an Agile Kanban…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **Revolución: A Side-Scroller Rpg For Learning The Philippine Spanish Revolution Through An Exciting And Educational Adventure** ([open thesis](http://localhost:5173/repository/eabd1c88-7956-4f2f-9c3f-35e943079ab1); UUID `eabd1c88-7956-4f2f-9c3f-35e943079ab1`)
  - Stored keywords: Educational Game, Game -Based Learning, Side -Scroller RPG, Godot Engine, Philippine Spanish Revolution, Interactive Learning, MEEGA+ Eval- uation Model, Pixel Art, Story-Based Learning, Grade 6 History Education
  - Abstract evidence: This study developed Revolución: A side-scroller RPG for Learning the Philippine-Spanish Revolution through an Exciting and Educational Adventure, to address learning about the Philippine -Spanish Revolution among Grade 6 students of Pulung Santol Elementary School. The researcher employed the…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **CyberDefender: A Game-Based Learning Platform for Enhancing Students' Cyber Threat Awareness** ([open thesis](http://localhost:5173/repository/10416ed7-4445-456d-9c4c-c9504765e40f); UUID `10416ed7-4445-456d-9c4c-c9504765e40f`)
  - Stored keywords: Cybersecurity, Roblox, Agile, ISO 25010
  - Abstract evidence: The educational game CyberDefender was developed with the aim of helping to solve the growing cybersecurity awareness problems among students, through the use of interactive game-based learning. This means finding innovative ways to increase their knowledge about the risk of cyber threats, which i…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______

### Health Informatics — 6 theses

**Cluster ID:** 7 · **Size badge:** EMERGING · **Leading TF-IDF terms:** barangay, health, healthcare, medical, digital, inventory

The name is an **unverified suggestion**. For each thesis, mark whether its research subject fits this group name. Check the source document if stored metadata looks wrong.

- **MedicScale: An Android Application for Patients’ Medical Chart** ([open thesis](http://localhost:5173/repository/57f8a9ca-b067-48b0-9c13-9eed8047f355); UUID `57f8a9ca-b067-48b0-9c13-9eed8047f355`)
  - Stored keywords: Medical, Record System, Electronic, Application, Hospital
  - Abstract evidence: MedicScale is an electronic medical record made to become a healthcare worker’s assistant. It is a mobile-based application that allows them to store and manage patients’ information and medical history. It will serve as the nurses’ companion whenever they do their rounds along with their…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **Web-Based Equipment Maintenance Monitoring System for DHVSU Facilities** ([open thesis](http://localhost:5173/repository/e5aac843-a9ed-4be6-a45e-64f29da466d8); UUID `e5aac843-a9ed-4be6-a45e-64f29da466d8`)
  - Stored keywords: QR code generator, QR scanner, Equipment requests
  - Abstract evidence: A web-based equipment maintenance monitoring and inventory system developed for the Procurement and Supply Management Office (PSMO) and facility custodians at Don Honorio Ventura State University. Utilizing Agile development and the Kanban framework with Laravel and MySQL, the system replaces…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **VAXTRACK: A WEB APPLICATION FOR RABIES VACCINATION TRACKING AND MANAGEMENT** ([open thesis](http://localhost:5173/repository/2db3a8d8-cf98-4f9e-bcb6-6f4390e069dd); UUID `2db3a8d8-cf98-4f9e-bcb6-6f4390e069dd`)
  - Stored keywords: Web Application, Animal bites, Public Health Concern, Vaccination Tracking and Management, VaxTrack, User-friendly, Accessible, Manage Animal Welfare Information, Rabies Prevention
  - Abstract evidence: A web-based rabies surveillance and pet immunization tracking application developed for local government health staff and barangay officials in the City of San Fernando, Pampanga. Developed using the Waterfall SDLC model, the platform digitizes rabies case reporting, multi-pet registration,…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **SINDALAN CONNECT: A NEXT GENERATION LOCAL COMMUNITY MANAGEMENT SYSTEM POWERED BY AI CHATBOT AND EMERGENCY RESPONSE** ([open thesis](http://localhost:5173/repository/7203d29b-4dba-4ede-aa25-335ef85707a5); UUID `7203d29b-4dba-4ede-aa25-335ef85707a5`)
  - Stored keywords: Barangay Information System, E-Governance, Digital Public Services, Emergency Response System, AI Chatbot, Incident Reporting, Online Permit Application, Rural Health Unit Announcements, Community Engagement
  - Abstract evidence: As people today expect faster, more convenient, and more responsive public services, the system brings together modern digital tools to improve how the barangay works and how it engages with the community. Sindalan Connect automates essential services like online permit applications, certificate…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **Rehirely: A Mobile-Based Application For Job-matching For Senior Citizen Employment** ([open thesis](http://localhost:5173/repository/c7d80880-8132-4163-b6fb-4ae63573e4ca); UUID `c7d80880-8132-4163-b6fb-4ae63573e4ca`)
  - Stored keywords: mobile application, job matching, digital inclusion, active aging, age - inclusive employment, employment technology, user-centered design, RAD methodology, ISO/IEC 25010
  - Abstract evidence: REHIRELY is a mobile -based job-matching application developed to help senior citizens aged 60 and above in Pampanga access local employment opportunities through a secure and user -friendly digital platform. The system was designed to address challenges such as digital exclusion and age-related…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **Barangaymed+: A Hybrid Application With Inventory And Healthcare Service System For Barangay Health Centers In Municipality Of Floridablanca, Pampanga** ([open thesis](http://localhost:5173/repository/942ded1d-9463-40d0-bdff-796f6add7f1d); UUID `942ded1d-9463-40d0-bdff-796f6add7f1d`)
  - Stored keywords: BarangayMed+, digital health, teleconsultation, inventory management, healthcare system, ISO/IEC 25010, barangay health centers
  - Abstract evidence: Barangay health centers serve as the primary access point for basic healthcare in the Philippines, yet many continue to depend on manual processes that result in long queues, inefficient record handling, delayed access to medicines, and limited communication with residents. This study developed…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______

### Mobile Applications (Cluster 3) — 5 theses

**Cluster ID:** 3 · **Size badge:** EMERGING · **Leading TF-IDF terms:** school, virtual, material, logic, respondents, android

The name is an **unverified suggestion**. For each thesis, mark whether its research subject fits this group name. Check the source document if stored metadata looks wrong.

- **Career Track Mobile Application Using Fuzzy Logic For High School Student** ([open thesis](http://localhost:5173/repository/a7e917cd-448a-46ab-8f69-d4d798f4865b); UUID `a7e917cd-448a-46ab-8f69-d4d798f4865b`)
  - Stored keywords: Holland Codes, Fuzzy Logic
  - Abstract evidence: The K to 12 programs include kindergarten through 12th grade, allowing students to acquire ideas and skills, develop lifelong learners, and prepare graduates for higher education, middle-level skill development, employment, and entrepreneurship. During the kindergarten -to-high school program,…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **“Simplify!” Android-Based Application: Improving Students’ Productivity by Scheduling and Organizing Tasks of Students** ([open thesis](http://localhost:5173/repository/de7b079a-1e63-44ef-ad33-95b87a581174); UUID `de7b079a-1e63-44ef-ad33-95b87a581174`)
  - Stored keywords: time management, schedule, organize, tasks, productivity, students
  - Abstract evidence: The thesis study titled, —Simplify! Android -Based Application: Improving Students‟ Productivity by Scheduling and Organizing Tasks of Students is designed for students to properly manage their school tasks and use their time efficiently. The application assists students in organizing academic…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **SIMULATION OF LOGIC GATES CIRCUITS TEST AND GUIDE USING ANDROID APPLICATION** ([open thesis](http://localhost:5173/repository/7912270e-6a1b-4cb8-baa7-16ac04b6df6a); UUID `7912270e-6a1b-4cb8-baa7-16ac04b6df6a`)
  - Stored keywords: Logic gates, simulator, application
  - Abstract evidence: Educational software is becoming increasingly significant in schools and colleges. In keeping with this trend, educational institutions are increasingly relying on mobile applications to help them develop, particularly in teaching and learning. The proponents of Logic Gate Operations have…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **ChemLab AR: AUGMENTED REALITY-BASED CHEMISTRY EXPERIMENTS** ([open thesis](http://localhost:5173/repository/e2d47493-770e-4d2a-bf73-c6c191258fe0); UUID `e2d47493-770e-4d2a-bf73-c6c191258fe0`)
  - Stored keywords: Augmented Reality (AR), Ball-and-Stick Models, Chemical Reaction, Chemistry Education, Molecular Geometry, Mobile Application, Virtual Laboratory, 3D Visualization
  - Abstract evidence: The lack of sufficient laboratory equipment in Philippine public schools significantly hinders the effective learning of general chemistry concepts such as molecular structures and chemical reactions. To take aim at this educational gap, the "ChemLab AR" Android mobile application was developed,…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **ARAL: An Android-based 3D Virtual Learning Material for Preschool Students** ([open thesis](http://localhost:5173/repository/a5d4a3d3-378c-4f59-b6f0-b3144cbc52e4); UUID `a5d4a3d3-378c-4f59-b6f0-b3144cbc52e4`)
  - Stored keywords: 3D, Android, C-sharp (C#), Platform, Unity3D, Virtual Learning Environment (V.L.E), Structured Query Language (SQL), Windows, XAMPP
  - Abstract evidence: The A.R.A.L. an Android-based 3D Virtual Learning Material for Preschool Students is a 3D Virtual and interactive learning material for visual presentation of alphabets, shapes, colors, and numbers. The study was proven an effective teaching aid for teachers and to use the 3D virtual learning…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______

### Web-Based Systems — 3 theses

**Cluster ID:** 6 · **Size badge:** UNDEREXPLORED · **Leading TF-IDF terms:** municipal, treasury, office, sms, monitoring, mswdo

The name is an **unverified suggestion**. For each thesis, mark whether its research subject fits this group name. Check the source document if stored metadata looks wrong.

- **E-pangasiwa: Data Dashboard for Business Establishment Monitoring for the Office of Municipal Treasury of the Municipality of Bacolor, Pampanga** ([open thesis](http://localhost:5173/repository/7ab3577d-8bf4-4a3d-b329-2d4852eb481a); UUID `7ab3577d-8bf4-4a3d-b329-2d4852eb481a`)
  - Stored keywords: track, monitor, data, dashboard, municipal treasury
  - Abstract evidence: A web-based data dashboard developed via Rapid Application Development (RAD) to modernize business establishment monitoring, permit applications, and tax revenue tracking for the Office of Municipal Treasury of Bacolor, Pampanga. The platform replaces paper records with interactive visual charts…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **SISTEMA de OBRA: TRAINING MONITORING SYSTEM** ([open thesis](http://localhost:5173/repository/53601b50-dde7-42bc-b1c2-a417a3f57cb3); UUID `53601b50-dde7-42bc-b1c2-a417a3f57cb3`)
  - Stored keywords: Sistema de Obra, Training Monitoring System, Agile Software, ISO, Web-Based Approach
  - Abstract evidence: Developed for the Municipal Social Welfare and Development Office (MSWDO) of Bacolor, Pampanga, Sistema de Obra is a web-based training monitoring and management platform designed to replace outdated paper and spreadsheet systems. Built through Agile software development, the platform streamlines…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **MSWD Online Financial Assistance Program Management System with SMS Notification and Status Tracking** ([open thesis](http://localhost:5173/repository/334eaf14-be5d-45a7-a8d2-5194f924bcf8); UUID `334eaf14-be5d-45a7-a8d2-5194f924bcf8`)
  - Stored keywords: MSWD, Online Financial Assistance, AICS, SMS, OTP, Status Tracking
  - Abstract evidence: A web-based application designed for the Municipal Social Welfare and Development Office (MSWDO) in Santo Tomas, Pampanga to digitize the Assistance to Individuals in Crisis Situations (AICS) program. Developed using an iterative methodology connecting the MSWDO, Budget, Accounting, and Treasury…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
  - **Source check:** Source caveat: the manuscript prints an HTEFinder/OJT abstract under its ABSTRACT heading; review that source mismatch before relying on the abstract for grouping.

## Weighted fields candidate

### Data Analytics — 8 theses

**Cluster ID:** 2 · **Size badge:** SATURATED · **Leading TF-IDF terms:** web-based, analytics, algorithm, data analytics, data, equipment

The name is an **unverified suggestion**. For each thesis, mark whether its research subject fits this group name. Check the source document if stored metadata looks wrong.

- **Thesix: Centralized Web-Based Capstone And Thesis Repository With Bert-Driven Semantic Similarity Algorithm** ([open thesis](http://localhost:5173/repository/667fe89e-c714-484f-aaaa-7e09b0557e6c); UUID `667fe89e-c714-484f-aaaa-7e09b0557e6c`)
  - Stored keywords: BERT, Capstone Repository, Semantic Similarity, Academic Innovation
  - Abstract evidence: The increasing volume of capstone and thesis projects in academic institutions necessitates a centralized and accessible repository to streamline management, accessibility, and visibility. Addressing this need, THESIX: Centralized Web -Based Capstone and Thesis Repository with BERT -Driven Semantic…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **APPOKO: A Web-Based Elderly Medication Monitoring System with Descriptive Analytics and GPS Tracking** ([open thesis](http://localhost:5173/repository/8fbe4f92-7420-477e-a16d-084927644b9c); UUID `8fbe4f92-7420-477e-a16d-084927644b9c`)
  - Stored keywords: Elderly healthcare management, web-based system, GPS tracking, Agile Software Development Methodology, Web-based Approach
  - Abstract evidence: The elderly care facility at Bahay Pag-ibig in Telabastagan, San Fernando, Pampanga, struggled to monitor residents and track medication due to a high resident-to-staff ratio, leaving administrators and caregivers unable to maintain healthcare management effectively with the limited workforce…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **ALUMNI PORTAL TRACKER WITH DATA ANALYTICS USING FOLD-GROWTH ALGORITHM** ([open thesis](http://localhost:5173/repository/ab97a031-f6b2-44e6-9a7e-6abcab04c809); UUID `ab97a031-f6b2-44e6-9a7e-6abcab04c809`)
  - Stored keywords: alumni portal, tracker, data analytics, fold-growth, algorithm, web based
  - Abstract evidence: Alumni Portal Tracker with Data Analytics using Fold-Growth Algorithm is a web-based Alumni Portal Tracker that enables the Don Honorio Ventura State University College of Computing Studies department in keeping and managing alumni records. It will serve as a useful interface for alumni and the d…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **Web-Based Qualifying Examination for Accountancy Students of Don Honorio Ventura State University – Main Campus** ([open thesis](http://localhost:5173/repository/11fdc7b9-4308-4e65-ac11-b57be86f8550); UUID `11fdc7b9-4308-4e65-ac11-b57be86f8550`)
  - Stored keywords: paper-based examination, web-based qualifying examination, digitized, database, data records, user-friendly, graphic user interface
  - Abstract evidence: Designed for the College of Business Studies at DHVSU Main Campus, this web-based examination platform digitizes the annual qualifying assessment for Bachelor of Science in Accountancy students. Developed using ASP.NET, SQL Server, and an Agile framework, the system replaces paper-based…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **Web-Based Equipment Maintenance Monitoring System for DHVSU Facilities** ([open thesis](http://localhost:5173/repository/e5aac843-a9ed-4be6-a45e-64f29da466d8); UUID `e5aac843-a9ed-4be6-a45e-64f29da466d8`)
  - Stored keywords: QR code generator, QR scanner, Equipment requests
  - Abstract evidence: A web-based equipment maintenance monitoring and inventory system developed for the Procurement and Supply Management Office (PSMO) and facility custodians at Don Honorio Ventura State University. Utilizing Agile development and the Kanban framework with Laravel and MySQL, the system replaces…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **Web-Based Grading System With Data Analytics For The Modernized Processing Of President’s And Dean’s Lists Candidates** ([open thesis](http://localhost:5173/repository/a634c87e-abe4-486c-b9d7-29f6fa9585a8); UUID `a634c87e-abe4-486c-b9d7-29f6fa9585a8`)
  - Stored keywords: web-based system, data analytics, manual processing, grade verification, Optical Character Recognition (OCR)
  - Abstract evidence: This study addresses the inefficiencies of the manual processing of President’s List (PL) and Dean’s List (DL) applications at Pampanga State University, which is time-consuming and prone to delays. A web-based system was developed to streamline registration, grade computation, verification,…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **My Honorian Buddy: A Web-Based Peer-Tutoring System For The Students Of Pampanga State University** ([open thesis](http://localhost:5173/repository/2784252f-6995-4ce5-be72-87dd0d1276f1); UUID `2784252f-6995-4ce5-be72-87dd0d1276f1`)
  - Stored keywords: peer-tutoring, web-based, content-based algorithm
  - Abstract evidence: The increasing integration of technology in education has amplified the need for personalized academic support, particularly in online learning environments. My Honorian Buddy is a web-based peer-tutoring system that connects students one-onone with suitable peer tutors using a content -based…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **iSecure: An Integrated Web-Based System for Base Access and Security Operations** ([open thesis](http://localhost:5173/repository/a23823a2-bda9-4a96-9ed4-085d0a24b6e7); UUID `a23823a2-bda9-4a96-9ed4-085d0a24b6e7`)
  - Stored keywords: iSecure, Access Control, RFID, Facial Recognition, OCR, Security Operations, ISO/IEC 25010, Agile Scrum
  - Abstract evidence: In areas that needs high security people often use outdated paper-based systems to track and archive record. This can, in turn, run into problems due to human error and inefficiencies. The goal of this project was to develop a web-based system named iSecure that automates security procedures in…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______

### Educational Technology — 8 theses

**Cluster ID:** 4 · **Size badge:** SATURATED · **Leading TF-IDF terms:** learning, game, educational, digital, awareness, programming

The name is an **unverified suggestion**. For each thesis, mark whether its research subject fits this group name. Check the source document if stored metadata looks wrong.

- **KlasikoPinas: Filipino Traditions and Mythical Creatures Digital Game** ([open thesis](http://localhost:5173/repository/fc64acbe-4a43-4d27-bb0f-76fb7e279caf); UUID `fc64acbe-4a43-4d27-bb0f-76fb7e279caf`)
  - Stored keywords: Filipino traditions, traditional games, mythical creatures, digital game, Godot engine, KlasikoPinas
  - Abstract evidence: A 2.5D educational game developed using the Godot Engine and Blender to preserve Filipino cultural identity by teaching traditional outdoor games and indigenous folklore. Built using an Agile Kanban workflow, the game translates traditional games like Palosebo, Sipa, Luksong Baka, and Langit Lupa…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **Mamalakaya: A Web-based HIV Awareness Campaign Site with an Educational Game and Testing Centers Directory** ([open thesis](http://localhost:5173/repository/d9078b46-77bb-425c-a996-524ae65b9f72); UUID `d9078b46-77bb-425c-a996-524ae65b9f72`)
  - Stored keywords: HIV, educational game, awareness, education, campaign
  - Abstract evidence: An automated public health campaign website designed to provide accessible HIV education, destigmatization resources, and healthcare linkage during the COVID-19 pandemic. Developed using Agile methodology, the platform provides multimedia instructional content, an interactive educational game, a…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **MODEYUL: An Educational Kapampangan Supplemental Game App for Grade 3 Students** ([open thesis](http://localhost:5173/repository/f765b44b-073e-42d0-b453-f975d592d3dd); UUID `f765b44b-073e-42d0-b453-f975d592d3dd`)
  - Stored keywords: Programming, Unity Software, C#, 2D, Game App
  - Abstract evidence: Developed during the COVID-19 pandemic, ModeYul is an offline, module-based 2D educational Android game application designed to help Grade 3 students learn the Kapampangan language and local culture. Built using the Waterfall methodology with Unity and C#, the system incorporates interactive…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **MEMOLOOP: A CUSTOMIZABLE DIGITAL LEARNING FLASHCARDS FOR MEMORIZATION ASSESSMENT** ([open thesis](http://localhost:5173/repository/2724801d-2dfe-43a7-a941-5d633374baa0); UUID `2724801d-2dfe-43a7-a941-5d633374baa0`)
  - Stored keywords: Digital Flashcards, MemoLoop mobile application, Learning and Memorizing Information
  - Abstract evidence: MemoLoop is an Android mobile digital flashcard application engineered to enhance active recall and long-term memory retention for Bachelor of Science in Biology students at DHVSU. Developed using Flutter, Dart, Laravel, and MySQL, the application implements the SuperMemo SM-2 spaced repetition…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **CODEQUEST: WHEN JAVA PROGRAMMING MEETS PLAYFUL LEARNING** ([open thesis](http://localhost:5173/repository/3970223e-18b9-45df-88a2-99a83abdee02); UUID `3970223e-18b9-45df-88a2-99a83abdee02`)
  - Stored keywords: Gamification, Blended, Engagement, Effectiveness
  - Abstract evidence: CodeQuest is an interactive, web-based 3D gamified educational platform developed to enhance Java programming instruction through a blended learning approach. Developed using React.js, Three.js, Node.js, and PostgreSQL under the Agile Scrum framework, the system integrates quest-based programming…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **Revolución: A Side-Scroller Rpg For Learning The Philippine Spanish Revolution Through An Exciting And Educational Adventure** ([open thesis](http://localhost:5173/repository/eabd1c88-7956-4f2f-9c3f-35e943079ab1); UUID `eabd1c88-7956-4f2f-9c3f-35e943079ab1`)
  - Stored keywords: Educational Game, Game -Based Learning, Side -Scroller RPG, Godot Engine, Philippine Spanish Revolution, Interactive Learning, MEEGA+ Eval- uation Model, Pixel Art, Story-Based Learning, Grade 6 History Education
  - Abstract evidence: This study developed Revolución: A side-scroller RPG for Learning the Philippine-Spanish Revolution through an Exciting and Educational Adventure, to address learning about the Philippine -Spanish Revolution among Grade 6 students of Pulung Santol Elementary School. The researcher employed the…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **CyberDefender: A Game-Based Learning Platform for Enhancing Students' Cyber Threat Awareness** ([open thesis](http://localhost:5173/repository/10416ed7-4445-456d-9c4c-c9504765e40f); UUID `10416ed7-4445-456d-9c4c-c9504765e40f`)
  - Stored keywords: Cybersecurity, Roblox, Agile, ISO 25010
  - Abstract evidence: The educational game CyberDefender was developed with the aim of helping to solve the growing cybersecurity awareness problems among students, through the use of interactive game-based learning. This means finding innovative ways to increase their knowledge about the risk of cyber threats, which i…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **ARAL: An Android-based 3D Virtual Learning Material for Preschool Students** ([open thesis](http://localhost:5173/repository/a5d4a3d3-378c-4f59-b6f0-b3144cbc52e4); UUID `a5d4a3d3-378c-4f59-b6f0-b3144cbc52e4`)
  - Stored keywords: 3D, Android, C-sharp (C#), Platform, Unity3D, Virtual Learning Environment (V.L.E), Structured Query Language (SQL), Windows, XAMPP
  - Abstract evidence: The A.R.A.L. an Android-based 3D Virtual Learning Material for Preschool Students is a 3D Virtual and interactive learning material for visual presentation of alphabets, shapes, colors, and numbers. The study was proven an effective teaching aid for teachers and to use the 3D virtual learning…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______

### Web-Based Systems (Cluster 7) — 6 theses

**Cluster ID:** 7 · **Size badge:** EMERGING · **Leading TF-IDF terms:** tracking, web, medical, management, cashless, centralized

The name is an **unverified suggestion**. For each thesis, mark whether its research subject fits this group name. Check the source document if stored metadata looks wrong.

- **Hubisko: Scholarship Management In Pampanga Through Centralized Automation** ([open thesis](http://localhost:5173/repository/4d01b7a0-e453-43de-b900-8b84c41d6f70); UUID `4d01b7a0-e453-43de-b900-8b84c41d6f70`)
  - Stored keywords: Web Based Automation System, Scholarship
  - Abstract evidence: Scholarship application and management in the Philippines, particularly within Pampanga, remains largely dependent on manual and paper-based processes, creating inefficiencies for both student applicants and scholarship providers and making it difficult to keep scholarship-related information…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **MedicScale: An Android Application for Patients’ Medical Chart** ([open thesis](http://localhost:5173/repository/57f8a9ca-b067-48b0-9c13-9eed8047f355); UUID `57f8a9ca-b067-48b0-9c13-9eed8047f355`)
  - Stored keywords: Medical, Record System, Electronic, Application, Hospital
  - Abstract evidence: MedicScale is an electronic medical record made to become a healthcare worker’s assistant. It is a mobile-based application that allows them to store and manage patients’ information and medical history. It will serve as the nurses’ companion whenever they do their rounds along with their…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **Sabiyahe: A Cashless Mobile-Based E-Jeepney Tracking And Seat Reservation System** ([open thesis](http://localhost:5173/repository/6486a500-ce43-45fb-9d9f-2e539fc86d41); UUID `6486a500-ce43-45fb-9d9f-2e539fc86d41`)
  - Stored keywords: E-Jeepney Tracking System, Seat Reservation, Cashless Payment
  - Abstract evidence: SaBiyahe: A mobile-based application is a system created for public commuting. Aims at easing the problem that is still occurring with the manual onboarding system of public utility jeepneys and vehicles (PUJ, PUV). With the use of the said system application commuters may engage boarding and E…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **MSWD Online Financial Assistance Program Management System with SMS Notification and Status Tracking** ([open thesis](http://localhost:5173/repository/334eaf14-be5d-45a7-a8d2-5194f924bcf8); UUID `334eaf14-be5d-45a7-a8d2-5194f924bcf8`)
  - Stored keywords: MSWD, Online Financial Assistance, AICS, SMS, OTP, Status Tracking
  - Abstract evidence: A web-based application designed for the Municipal Social Welfare and Development Office (MSWDO) in Santo Tomas, Pampanga to digitize the Assistance to Individuals in Crisis Situations (AICS) program. Developed using an iterative methodology connecting the MSWDO, Budget, Accounting, and Treasury…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
  - **Source check:** Source caveat: the manuscript prints an HTEFinder/OJT abstract under its ABSTRACT heading; review that source mismatch before relying on the abstract for grouping.
- **VAXTRACK: A WEB APPLICATION FOR RABIES VACCINATION TRACKING AND MANAGEMENT** ([open thesis](http://localhost:5173/repository/2db3a8d8-cf98-4f9e-bcb6-6f4390e069dd); UUID `2db3a8d8-cf98-4f9e-bcb6-6f4390e069dd`)
  - Stored keywords: Web Application, Animal bites, Public Health Concern, Vaccination Tracking and Management, VaxTrack, User-friendly, Accessible, Manage Animal Welfare Information, Rabies Prevention
  - Abstract evidence: A web-based rabies surveillance and pet immunization tracking application developed for local government health staff and barangay officials in the City of San Fernando, Pampanga. Developed using the Waterfall SDLC model, the platform digitizes rabies case reporting, multi-pet registration,…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **Headlink: An Iot-Powered Head Pose Tracking System For Assistive Input And Human-Computer Interaction** ([open thesis](http://localhost:5173/repository/1bb71d5b-494c-452b-89e3-28ecafd4a81a); UUID `1bb71d5b-494c-452b-89e3-28ecafd4a81a`)
  - Stored keywords: Head Pose Tracking, Assistive Technologies, Human-Computer Interaction, Gesture-Based Inputs, Raspberry Pi, IoT System
  - Abstract evidence: HeadLink is an IoT-Powered Head Pose tracking system designed to make computers more accessible by providing a hands-free alternative for human-computer interaction. It uses computer vision and facial landmarking to track head position and translate it into mouse movements and functions. HeadLink…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______

### Web-Based Systems (Cluster 9) — 6 theses

**Cluster ID:** 9 · **Size badge:** EMERGING · **Leading TF-IDF terms:** management, mapping, tasks, productivity, city, supply

The name is an **unverified suggestion**. For each thesis, mark whether its research subject fits this group name. Check the source document if stored metadata looks wrong.

- **“Simplify!” Android-Based Application: Improving Students’ Productivity by Scheduling and Organizing Tasks of Students** ([open thesis](http://localhost:5173/repository/de7b079a-1e63-44ef-ad33-95b87a581174); UUID `de7b079a-1e63-44ef-ad33-95b87a581174`)
  - Stored keywords: time management, schedule, organize, tasks, productivity, students
  - Abstract evidence: The thesis study titled, —Simplify! Android -Based Application: Improving Students‟ Productivity by Scheduling and Organizing Tasks of Students is designed for students to properly manage their school tasks and use their time efficiently. The application assists students in organizing academic…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **Vehicle Management System using Cloud Mapping Technology** ([open thesis](http://localhost:5173/repository/ad4f3076-3c4e-4f73-b54a-2b6f97c485e4); UUID `ad4f3076-3c4e-4f73-b54a-2b6f97c485e4`)
  - Stored keywords: cloud server, mapping
  - Abstract evidence: Due to pandemic, limited transportation led to decrease in overall economic status of a country. In the Philippines, where most of the transactions were traditional, the said transportation industries had to adapt to the current situation. Through the help of the internet and newest web…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **COMPAWNION: A PROFILE MANAGEMENT SYSTEM with GEO-LOCATION SYSTEM for NOAH'S ARK DOG AND CAT SHELTER, MABALACAT, PAMPANGA** ([open thesis](http://localhost:5173/repository/f92512f4-5976-4844-bc95-fcbb77f47f7b); UUID `f92512f4-5976-4844-bc95-fcbb77f47f7b`)
  - Stored keywords: Geo-location, Profile Management, Stray pets, Dogs, Cats, Mabalacat City
  - Abstract evidence: Compawnion is a web-based animal profile and rescue management platform created for Noah's Ark Dog and Cat Shelter in Mabalacat City, Pampanga. Developed through an iterative software lifecycle, the system digitalizes sheltered pet records, coordinates adoption applications and donations, tracks…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **TASKGROVE: A TREE-BASED PROJECT MANAGEMENT APPLICATION** ([open thesis](http://localhost:5173/repository/fd8a1ca0-665f-442b-b919-7afe31cdbbc5); UUID `fd8a1ca0-665f-442b-b919-7afe31cdbbc5`)
  - Stored keywords: project management, tree-based, task management, monitoring
  - Abstract evidence: TaskGrove is an online platform that is essential in today's project management landscape. Its emergence has brought about a significant revolution in the way tasks are organized within project frameworks, leading to a remarkable increase in productivity levels. This innovative platform not only…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **ANIDELIVERY: A FARMERS PLATFORM FOR SUSTAINABLE AGRICULTURE THROUGH MACHINE LEARNING-POWERED DIGITAL MARKETPLACE IN PAMPANGA** ([open thesis](http://localhost:5173/repository/143fb188-2e1a-41f9-8400-ca42466fd8a3); UUID `143fb188-2e1a-41f9-8400-ca42466fd8a3`)
  - Stored keywords: AniDelivery, Digital Marketplace, Supply Chain Management, Over Supply, Under Supply, Consumer
  - Abstract evidence: A mobile and web-based digital marketplace created to support sustainable agriculture in Pampanga by facilitating direct transactions between farmers and consumers. Developed using an Agile Scrum methodology, the platform incorporates machine learning algorithms for sales forecasting to mitigate…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **Development of Complaints and Grievances Management System Aligned with R.A. No. 11313** ([open thesis](http://localhost:5173/repository/2c902b58-ba62-4198-b663-fc72afbec25c); UUID `2c902b58-ba62-4198-b663-fc72afbec25c`)
  - Stored keywords: Case Management, Republic Act No. 11313, Safe Spaces Act, Web-Based System, Grievance Management, Gender-Based Sexual Harassment, ISO/IEC 25010
  - Abstract evidence: This study addresses the ongoing problems within Pampanga State University, particularly in the College of Computing Studies, which manages the complaint filing, delayed process, privacy violation, and unsettled cases for taking legal actions. To resolve these issues, the researchers developed a…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______

### Internet of Things — 5 theses

**Cluster ID:** 5 · **Size badge:** EMERGING · **Leading TF-IDF terms:** smart, irrigation, analysis, water, iot, intelligent

The name is an **unverified suggestion**. For each thesis, mark whether its research subject fits this group name. Check the source document if stored metadata looks wrong.

- **THESYS+: A Semantic-Based Thesis Retrieval and Topic Trend Analysis System for CCS Undergraduate Theses at Pampanga State University** ([open thesis](http://localhost:5173/repository/dfd4a0cd-482f-4ad4-bb67-a8d356655640); UUID `dfd4a0cd-482f-4ad4-bb67-a8d356655640`)
  - Stored keywords: none
  - Abstract evidence: Traditional academic repositories rely on keyword-based searches, making it difficult to detect semantic topic redundancies or track research trajectories over time. To address this, THESYS+ was developed as an intelligent thesis retrieval and topic trend analysis platform for the College of…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
  - **Source check:** No stored keywords; inspect the source if this affects the topic.
- **ANTABE: AN INTELLIGENT GUIDE STICK FOR VISUALLY IMPAIRED** ([open thesis](http://localhost:5173/repository/b05abf84-2643-4d03-888b-80fdb187152d); UUID `b05abf84-2643-4d03-888b-80fdb187152d`)
  - Stored keywords: Visual Impairment, Smart Cane, Assistive Technology, Iot
  - Abstract evidence: Antabe is an intelligent assistive guide stick designed to enhance spatial awareness, obstacle avoidance, and independent mobility for visually impaired individuals in Guagua, Pampanga. Powered by an Arduino microcontroller, the device integrates ultrasonic sensors for multi-directional obstacle…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **AQUAFLOW: AN ARDUINO-POWERED SMART IRRIGATION SYSTEM FOR GUMAIN DAM** ([open thesis](http://localhost:5173/repository/22f74b8e-7c13-4714-bab3-67e10140965d); UUID `22f74b8e-7c13-4714-bab3-67e10140965d`)
  - Stored keywords: Smart Irrigation System, Arduino Technology, Blynk Application, IoT (Internet of Things), Water Flow Control, Water Level Monitoring
  - Abstract evidence: AquaFlow is an IoT-based automated irrigation system developed for agricultural fields connected to Gumain Dam in Floridablanca, Pampanga to reduce water wastage and prevent crop damage from overwatering or drought stress. Built through Rapid Application Development (RAD), the system integrates a…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **ShopEase: AN IOT-BASED SHOPPING CART WITH BARCODE SCANNER AND REAL-TIME MULTI-CART MONITORING SYSTEM** ([open thesis](http://localhost:5173/repository/3ee906b3-2e8d-4da9-b155-5a70c69ba4fa); UUID `3ee906b3-2e8d-4da9-b155-5a70c69ba4fa`)
  - Stored keywords: IoT (Internet of Things), Real-Time Monitoring, Multiple Carts, Cashier Application
  - Abstract evidence: Traditional supermarket checkout methods create significant friction for customers, often resulting in long queues and reduced operational efficiency. To resolve these challenges, this study developed ShopEase: An IoT-Based Shopping Cart with Barcode Scann er and Real-Time Multi-Cart Monitoring…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **AnImo: An AI-Driven Agricultural Hybrid Platform with Intelligent Crop Recommendations and IoT-Enabled Solar-Powered Water Irrigation Based on Soil Analysis** ([open thesis](http://localhost:5173/repository/b1f3b63d-16ce-4458-8224-163564b61a8a); UUID `b1f3b63d-16ce-4458-8224-163564b61a8a`)
  - Stored keywords: Gemini, Internet of Things, Smart Farming, Solar -Powered Water Pump, Soil Analysis
  - Abstract evidence: Local farmers in the Philippines face significant challenges, including fluctuating market prices, soil degradation, and climate variability, which contribute to low productivity and economic losses. Addressing the urgent need for innovative technological solutions, this project developed AnImo: An…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______

### Web-Based Systems (Cluster 3) — 4 theses

**Cluster ID:** 3 · **Size badge:** EMERGING · **Leading TF-IDF terms:** training, geofencing, geofencing technology, technology, monitoring, treasury

The name is an **unverified suggestion**. For each thesis, mark whether its research subject fits this group name. Check the source document if stored metadata looks wrong.

- **E-pangasiwa: Data Dashboard for Business Establishment Monitoring for the Office of Municipal Treasury of the Municipality of Bacolor, Pampanga** ([open thesis](http://localhost:5173/repository/7ab3577d-8bf4-4a3d-b329-2d4852eb481a); UUID `7ab3577d-8bf4-4a3d-b329-2d4852eb481a`)
  - Stored keywords: track, monitor, data, dashboard, municipal treasury
  - Abstract evidence: A web-based data dashboard developed via Rapid Application Development (RAD) to modernize business establishment monitoring, permit applications, and tax revenue tracking for the Office of Municipal Treasury of Bacolor, Pampanga. The platform replaces paper records with interactive visual charts…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **SISTEMA de OBRA: TRAINING MONITORING SYSTEM** ([open thesis](http://localhost:5173/repository/53601b50-dde7-42bc-b1c2-a417a3f57cb3); UUID `53601b50-dde7-42bc-b1c2-a417a3f57cb3`)
  - Stored keywords: Sistema de Obra, Training Monitoring System, Agile Software, ISO, Web-Based Approach
  - Abstract evidence: Developed for the Municipal Social Welfare and Development Office (MSWDO) of Bacolor, Pampanga, Sistema de Obra is a web-based training monitoring and management platform designed to replace outdated paper and spreadsheet systems. Built through Agile software development, the platform streamlines…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **DORMIFY: DORM FINDER AND MANAGEMENT SYSTEM WITH GEOFENCING TECHNOLOGY FOR DHVSU MAIN CAMPUS** ([open thesis](http://localhost:5173/repository/827a721c-0ecc-4896-b9b4-f5571f32736c); UUID `827a721c-0ecc-4896-b9b4-f5571f32736c`)
  - Stored keywords: Dorm Finder, Management System, Geofencing Technology
  - Abstract evidence: Dormify is an Android-based dormitory finder and rental management system created for students, faculty, and property owners within a 1-kilometer radius of DHVSU Main Campus in Bacolor, Pampanga. Developed using an iterative model, the application incorporates Google Maps geofencing to display…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **HTEFinder: A Web Application Utilizing Geofencing Technology** ([open thesis](http://localhost:5173/repository/ca211b67-2032-48e0-90d8-d30c250a7804); UUID `ca211b67-2032-48e0-90d8-d30c250a7804`)
  - Stored keywords: On-the-Job Training, Host Training Establishment, Geofencing Technology, Expert System, Laravel Framework, MySQL Database
  - Abstract evidence: HTEFinder is a web-based platform developed to streamline the search and placement process of Host Training Establishments (HTE) for on-the-job training (OJT) students in the College of Computing Studies at DHVSU. Developed with the Laravel framework and MySQL using an iterative approach, the…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______

### Mobile Applications (Cluster 8) — 4 theses

**Cluster ID:** 8 · **Size badge:** EMERGING · **Leading TF-IDF terms:** mobile, educational, emergency, virtual, complaint, visualization

The name is an **unverified suggestion**. For each thesis, mark whether its research subject fits this group name. Check the source document if stored metadata looks wrong.

- **#31B: A 117 Emergency Communication Platform For Abuse Report In A Mobile Application** ([open thesis](http://localhost:5173/repository/b34020a4-99ff-4087-a7f8-09b9690e4063); UUID `b34020a4-99ff-4087-a7f8-09b9690e4063`)
  - Stored keywords: Domestic Abuse, Complaint, Mobile Application, VAWC
  - Abstract evidence: The proposed study aims to establish an idea of a free communication platform for the victims of abuse, that is user-friendly, with much better assistance and immediate response, with the help and support from the local authorities and social services. It would also be a big help to promote…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **CYBERESCAPE: A MOBILE EDUCATIONAL ESCAPE ROOM APPLICATION FOR NETWORKING FUNDAMENTALS** ([open thesis](http://localhost:5173/repository/8a1b73df-d71c-4458-82c9-b9721f655b94); UUID `8a1b73df-d71c-4458-82c9-b9721f655b94`)
  - Stored keywords: CyberEscape mobile game application, Educational mobile game, Digital Educational Escape Room, Gamified Learning
  - Abstract evidence: CyberEscape is an educational 2D mobile escape room game developed to improve comprehension of networking fundamentals among TVL-ICT Senior High School students at Tomas Dizon Foundation Institute. Built using Unity, C#, Aseprite, and the Octalysis gamification framework under an Agile Kanban…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **SINDALAN CONNECT: A NEXT GENERATION LOCAL COMMUNITY MANAGEMENT SYSTEM POWERED BY AI CHATBOT AND EMERGENCY RESPONSE** ([open thesis](http://localhost:5173/repository/7203d29b-4dba-4ede-aa25-335ef85707a5); UUID `7203d29b-4dba-4ede-aa25-335ef85707a5`)
  - Stored keywords: Barangay Information System, E-Governance, Digital Public Services, Emergency Response System, AI Chatbot, Incident Reporting, Online Permit Application, Rural Health Unit Announcements, Community Engagement
  - Abstract evidence: As people today expect faster, more convenient, and more responsive public services, the system brings together modern digital tools to improve how the barangay works and how it engages with the community. Sindalan Connect automates essential services like online permit applications, certificate…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **ChemLab AR: AUGMENTED REALITY-BASED CHEMISTRY EXPERIMENTS** ([open thesis](http://localhost:5173/repository/e2d47493-770e-4d2a-bf73-c6c191258fe0); UUID `e2d47493-770e-4d2a-bf73-c6c191258fe0`)
  - Stored keywords: Augmented Reality (AR), Ball-and-Stick Models, Chemical Reaction, Chemistry Education, Molecular Geometry, Mobile Application, Virtual Laboratory, 3D Visualization
  - Abstract evidence: The lack of sufficient laboratory equipment in Philippine public schools significantly hinders the effective learning of general chemistry concepts such as molecular structures and chemical reactions. To take aim at this educational gap, the "ChemLab AR" Android mobile application was developed,…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______

### Natural Language Processing — 3 theses

**Cluster ID:** 1 · **Size badge:** EMERGING · **Leading TF-IDF terms:** health, language processing, natural, natural language, processing, language

The name is an **unverified suggestion**. For each thesis, mark whether its research subject fits this group name. Check the source document if stored metadata looks wrong.

- **EXTHEALTH: A BROWSER EXTENSION FOR HEALTH INFORMATION ON X USING NATURAL LANGUAGE PROCESSING (NLP)** ([open thesis](http://localhost:5173/repository/8069344d-5287-40de-8e51-176fb13b8d2a); UUID `8069344d-5287-40de-8e51-176fb13b8d2a`)
  - Stored keywords: Health Misinformation, Browser Extension, Fact-checking, X, Twitter, Social Media
  - Abstract evidence: Many social media users lack the time or motivation to fact-check health-related claims they encounter online, allowing health misinformation to spread widely on platforms such as X (formerly Twitter). This study presents eXtHealth, a browser extension that uses Natural Language Processing (NLP) to…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **DHVCHAT: A WEB-BASED INTELLIGENT CHAT ASSISTANT FOR THE ADMISSIONS OFFICE USING NATURAL LANGUAGE PROCESSING** ([open thesis](http://localhost:5173/repository/18737b6e-983a-4ae6-915a-8f155aefb160); UUID `18737b6e-983a-4ae6-915a-8f155aefb160`)
  - Stored keywords: Natural Language Processing, chatbots, university admission, AI-enhanced communication systems
  - Abstract evidence: DHVChat is an AI-powered conversational web assistant created for the Admissions Office of Don Honorio Ventura State University to automate student inquiry handling. Built using ReactJS, Python, and OpenAI's GPT-3.5 Turbo text embeddings within an iterative waterfall methodology, the system…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **Barangaymed+: A Hybrid Application With Inventory And Healthcare Service System For Barangay Health Centers In Municipality Of Floridablanca, Pampanga** ([open thesis](http://localhost:5173/repository/942ded1d-9463-40d0-bdff-796f6add7f1d); UUID `942ded1d-9463-40d0-bdff-796f6add7f1d`)
  - Stored keywords: BarangayMed+, digital health, teleconsultation, inventory management, healthcare system, ISO/IEC 25010, barangay health centers
  - Abstract evidence: Barangay health centers serve as the primary access point for basic healthcare in the Philippines, yet many continue to depend on manual processes that result in long queues, inefficient record handling, delayed access to medicines, and limited communication with residents. This study developed…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______

### Mobile Applications (Cluster 6) — 3 theses

**Cluster ID:** 6 · **Size badge:** EMERGING · **Leading TF-IDF terms:** matching, employment, dormitory, senior, mobile, mobile-based

The name is an **unverified suggestion**. For each thesis, mark whether its research subject fits this group name. Check the source document if stored metadata looks wrong.

- **Rehirely: A Mobile-Based Application For Job-matching For Senior Citizen Employment** ([open thesis](http://localhost:5173/repository/c7d80880-8132-4163-b6fb-4ae63573e4ca); UUID `c7d80880-8132-4163-b6fb-4ae63573e4ca`)
  - Stored keywords: mobile application, job matching, digital inclusion, active aging, age - inclusive employment, employment technology, user-centered design, RAD methodology, ISO/IEC 25010
  - Abstract evidence: REHIRELY is a mobile -based job-matching application developed to help senior citizens aged 60 and above in Pampanga access local employment opportunities through a secure and user -friendly digital platform. The system was designed to address challenges such as digital exclusion and age-related…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **Attachmates: A Dating App For Ai-Powered Compatibility-Based Matching Through Attachments Styles And Love Languages** ([open thesis](http://localhost:5173/repository/c1b8c2f6-69c3-47f6-80cb-ecaa3fb79c1c); UUID `c1b8c2f6-69c3-47f6-80cb-ecaa3fb79c1c`)
  - Stored keywords: attachment styles, love languages, dating fatigue, hybrid recommendation system, psychology-based matching, Flutter, Firebase, AI matching
  - Abstract evidence: Many dating applications today prioritize physical appearance and fast interactions, often leading to emotional mismatches, inconsistent connections, and dating fatigue among users. This study focused on development of AttachMates, a dating application designed to improve compatibility by…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **DormHonorio: DORMITORY BOOKING AND ALGORITHM-DRIVEN ROOMMATE MATCHING MOBILE APPLICATION FOR HONORIANS** ([open thesis](http://localhost:5173/repository/7aa5c31d-8be0-4e1b-b4aa-1b6a87bb016c); UUID `7aa5c31d-8be0-4e1b-b4aa-1b6a87bb016c`)
  - Stored keywords: weighted scoring algorithm, roommate matching, dormitory, tenant
  - Abstract evidence: The goal of this study was to develop DormHonorio, a mobile application that helps Pampanga State University students find dormitories and compatible roommates in a more organized and reliable way. Since there is still no official online platform for this purpose, students often experience a…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______

### Mobile Applications (Cluster 11) — 3 theses

**Cluster ID:** 11 · **Size badge:** EMERGING · **Leading TF-IDF terms:** logic, fuzzy, fuzzy logic, mobile, farming, test

The name is an **unverified suggestion**. For each thesis, mark whether its research subject fits this group name. Check the source document if stored metadata looks wrong.

- **Career Track Mobile Application Using Fuzzy Logic For High School Student** ([open thesis](http://localhost:5173/repository/a7e917cd-448a-46ab-8f69-d4d798f4865b); UUID `a7e917cd-448a-46ab-8f69-d4d798f4865b`)
  - Stored keywords: Holland Codes, Fuzzy Logic
  - Abstract evidence: The K to 12 programs include kindergarten through 12th grade, allowing students to acquire ideas and skills, develop lifelong learners, and prepare graduates for higher education, middle-level skill development, employment, and entrepreneurship. During the kindergarten -to-high school program,…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **SIMULATION OF LOGIC GATES CIRCUITS TEST AND GUIDE USING ANDROID APPLICATION** ([open thesis](http://localhost:5173/repository/7912270e-6a1b-4cb8-baa7-16ac04b6df6a); UUID `7912270e-6a1b-4cb8-baa7-16ac04b6df6a`)
  - Stored keywords: Logic gates, simulator, application
  - Abstract evidence: Educational software is becoming increasingly significant in schools and colleges. In keeping with this trend, educational institutions are increasingly relying on mobile applications to help them develop, particularly in teaching and learning. The proponents of Logic Gate Operations have…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **A FUZZY LOGIC-BASED MOBILE APPLICATION FOR REAL-TIME MONITORING OF MODULAR INDOOR FARMING** ([open thesis](http://localhost:5173/repository/8212ab33-5c0e-4b1f-8383-583f1db45722); UUID `8212ab33-5c0e-4b1f-8383-583f1db45722`)
  - Stored keywords: Aeroponics, fuzzy logic algorithm, indoor
  - Abstract evidence: An automated indoor aeroponics system and mobile application developed to monitor and manage crucial plant environmental parameters, including temperature, humidity, pH, and water levels. Developed using a Waterfall model for the mobile app and a prototype model for the tower hardware, the system…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______

### Mobile Applications (Cluster 10) — 2 theses

**Cluster ID:** 10 · **Size badge:** UNDEREXPLORED · **Leading TF-IDF terms:** market, online market, online, supply, android, farmers

The name is an **unverified suggestion**. For each thesis, mark whether its research subject fits this group name. Check the source document if stored metadata looks wrong.

- **ARADA: AN ANDROID ONLINE MARKET WITH SUPPLY- DEMAND STATISTICS FOR SELECTED LOCAL FARMERS AND SUPPLIERS IN PAMPANGA** ([open thesis](http://localhost:5173/repository/9ae051ee-b6b5-4df2-9d03-876f594045f9); UUID `9ae051ee-b6b5-4df2-9d03-876f594045f9`)
  - Stored keywords: Farmer‟s Market, Supply -Demand Statistics, Public Market, Android Application, CoVid-19
  - Abstract evidence: Agriculture is vital to the Philippines' economy where it is among the nation’s major industries. On the other hand, Pampanga is a province where one of its main industries is agriculture. Most farmers’ selling locations are in local markets. However, due to Covid-19, travel restrictions were…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **PALE-NGKIHAN: ONLINE MARKET SYSTEM FOR ARAYAT RICE TRADERS** ([open thesis](http://localhost:5173/repository/9ade9f3c-ffde-4481-be98-b2605cc3abf1); UUID `9ade9f3c-ffde-4481-be98-b2605cc3abf1`)
  - Stored keywords: online market system, web-based, agricultural, rice trading, middlemen
  - Abstract evidence: A web-based e-commerce platform designed to establish a direct trading channel between rice farmers and buyers in Arayat, Pampanga. Developed using Agile methodology, the system eliminates price disparities caused by intermediaries by providing transparent pricing, product cataloging, order…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______

## Weighted, subject-oriented candidate

### Web-Based Systems (Cluster 2) — 6 theses

**Cluster ID:** 2 · **Size badge:** EMERGING · **Leading TF-IDF terms:** management, mapping, centralized, tasks, productivity, city

The name is an **unverified suggestion**. For each thesis, mark whether its research subject fits this group name. Check the source document if stored metadata looks wrong.

- **Hubisko: Scholarship Management In Pampanga Through Centralized Automation** ([open thesis](http://localhost:5173/repository/4d01b7a0-e453-43de-b900-8b84c41d6f70); UUID `4d01b7a0-e453-43de-b900-8b84c41d6f70`)
  - Stored keywords: Web Based Automation System, Scholarship
  - Abstract evidence: Scholarship application and management in the Philippines, particularly within Pampanga, remains largely dependent on manual and paper-based processes, creating inefficiencies for both student applicants and scholarship providers and making it difficult to keep scholarship-related information…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **“Simplify!” Android-Based Application: Improving Students’ Productivity by Scheduling and Organizing Tasks of Students** ([open thesis](http://localhost:5173/repository/de7b079a-1e63-44ef-ad33-95b87a581174); UUID `de7b079a-1e63-44ef-ad33-95b87a581174`)
  - Stored keywords: time management, schedule, organize, tasks, productivity, students
  - Abstract evidence: The thesis study titled, —Simplify! Android -Based Application: Improving Students‟ Productivity by Scheduling and Organizing Tasks of Students is designed for students to properly manage their school tasks and use their time efficiently. The application assists students in organizing academic…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **Vehicle Management System using Cloud Mapping Technology** ([open thesis](http://localhost:5173/repository/ad4f3076-3c4e-4f73-b54a-2b6f97c485e4); UUID `ad4f3076-3c4e-4f73-b54a-2b6f97c485e4`)
  - Stored keywords: cloud server, mapping
  - Abstract evidence: Due to pandemic, limited transportation led to decrease in overall economic status of a country. In the Philippines, where most of the transactions were traditional, the said transportation industries had to adapt to the current situation. Through the help of the internet and newest web…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **COMPAWNION: A PROFILE MANAGEMENT SYSTEM with GEO-LOCATION SYSTEM for NOAH'S ARK DOG AND CAT SHELTER, MABALACAT, PAMPANGA** ([open thesis](http://localhost:5173/repository/f92512f4-5976-4844-bc95-fcbb77f47f7b); UUID `f92512f4-5976-4844-bc95-fcbb77f47f7b`)
  - Stored keywords: Geo-location, Profile Management, Stray pets, Dogs, Cats, Mabalacat City
  - Abstract evidence: Compawnion is a web-based animal profile and rescue management platform created for Noah's Ark Dog and Cat Shelter in Mabalacat City, Pampanga. Developed through an iterative software lifecycle, the system digitalizes sheltered pet records, coordinates adoption applications and donations, tracks…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **TASKGROVE: A TREE-BASED PROJECT MANAGEMENT APPLICATION** ([open thesis](http://localhost:5173/repository/fd8a1ca0-665f-442b-b919-7afe31cdbbc5); UUID `fd8a1ca0-665f-442b-b919-7afe31cdbbc5`)
  - Stored keywords: project management, tree-based, task management, monitoring
  - Abstract evidence: TaskGrove is an online platform that is essential in today's project management landscape. Its emergence has brought about a significant revolution in the way tasks are organized within project frameworks, leading to a remarkable increase in productivity levels. This innovative platform not only…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **Development of Complaints and Grievances Management System Aligned with R.A. No. 11313** ([open thesis](http://localhost:5173/repository/2c902b58-ba62-4198-b663-fc72afbec25c); UUID `2c902b58-ba62-4198-b663-fc72afbec25c`)
  - Stored keywords: Case Management, Republic Act No. 11313, Safe Spaces Act, Web-Based System, Grievance Management, Gender-Based Sexual Harassment, ISO/IEC 25010
  - Abstract evidence: This study addresses the ongoing problems within Pampanga State University, particularly in the College of Computing Studies, which manages the complaint filing, delayed process, privacy violation, and unsettled cases for taking legal actions. To resolve these issues, the researchers developed a…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______

### Educational Technology — 6 theses

**Cluster ID:** 5 · **Size badge:** EMERGING · **Leading TF-IDF terms:** game, educational, digital, learning, educational game, grade

The name is an **unverified suggestion**. For each thesis, mark whether its research subject fits this group name. Check the source document if stored metadata looks wrong.

- **KlasikoPinas: Filipino Traditions and Mythical Creatures Digital Game** ([open thesis](http://localhost:5173/repository/fc64acbe-4a43-4d27-bb0f-76fb7e279caf); UUID `fc64acbe-4a43-4d27-bb0f-76fb7e279caf`)
  - Stored keywords: Filipino traditions, traditional games, mythical creatures, digital game, Godot engine, KlasikoPinas
  - Abstract evidence: A 2.5D educational game developed using the Godot Engine and Blender to preserve Filipino cultural identity by teaching traditional outdoor games and indigenous folklore. Built using an Agile Kanban workflow, the game translates traditional games like Palosebo, Sipa, Luksong Baka, and Langit Lupa…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **Mamalakaya: A Web-based HIV Awareness Campaign Site with an Educational Game and Testing Centers Directory** ([open thesis](http://localhost:5173/repository/d9078b46-77bb-425c-a996-524ae65b9f72); UUID `d9078b46-77bb-425c-a996-524ae65b9f72`)
  - Stored keywords: HIV, educational game, awareness, education, campaign
  - Abstract evidence: An automated public health campaign website designed to provide accessible HIV education, destigmatization resources, and healthcare linkage during the COVID-19 pandemic. Developed using Agile methodology, the platform provides multimedia instructional content, an interactive educational game, a…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **MODEYUL: An Educational Kapampangan Supplemental Game App for Grade 3 Students** ([open thesis](http://localhost:5173/repository/f765b44b-073e-42d0-b453-f975d592d3dd); UUID `f765b44b-073e-42d0-b453-f975d592d3dd`)
  - Stored keywords: Programming, Unity Software, C#, 2D, Game App
  - Abstract evidence: Developed during the COVID-19 pandemic, ModeYul is an offline, module-based 2D educational Android game application designed to help Grade 3 students learn the Kapampangan language and local culture. Built using the Waterfall methodology with Unity and C#, the system incorporates interactive…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **CYBERESCAPE: A MOBILE EDUCATIONAL ESCAPE ROOM APPLICATION FOR NETWORKING FUNDAMENTALS** ([open thesis](http://localhost:5173/repository/8a1b73df-d71c-4458-82c9-b9721f655b94); UUID `8a1b73df-d71c-4458-82c9-b9721f655b94`)
  - Stored keywords: CyberEscape mobile game application, Educational mobile game, Digital Educational Escape Room, Gamified Learning
  - Abstract evidence: CyberEscape is an educational 2D mobile escape room game developed to improve comprehension of networking fundamentals among TVL-ICT Senior High School students at Tomas Dizon Foundation Institute. Built using Unity, C#, Aseprite, and the Octalysis gamification framework under an Agile Kanban…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **MEMOLOOP: A CUSTOMIZABLE DIGITAL LEARNING FLASHCARDS FOR MEMORIZATION ASSESSMENT** ([open thesis](http://localhost:5173/repository/2724801d-2dfe-43a7-a941-5d633374baa0); UUID `2724801d-2dfe-43a7-a941-5d633374baa0`)
  - Stored keywords: Digital Flashcards, MemoLoop mobile application, Learning and Memorizing Information
  - Abstract evidence: MemoLoop is an Android mobile digital flashcard application engineered to enhance active recall and long-term memory retention for Bachelor of Science in Biology students at DHVSU. Developed using Flutter, Dart, Laravel, and MySQL, the application implements the SuperMemo SM-2 spaced repetition…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **Revolución: A Side-Scroller Rpg For Learning The Philippine Spanish Revolution Through An Exciting And Educational Adventure** ([open thesis](http://localhost:5173/repository/eabd1c88-7956-4f2f-9c3f-35e943079ab1); UUID `eabd1c88-7956-4f2f-9c3f-35e943079ab1`)
  - Stored keywords: Educational Game, Game -Based Learning, Side -Scroller RPG, Godot Engine, Philippine Spanish Revolution, Interactive Learning, MEEGA+ Eval- uation Model, Pixel Art, Story-Based Learning, Grade 6 History Education
  - Abstract evidence: This study developed Revolución: A side-scroller RPG for Learning the Philippine-Spanish Revolution through an Exciting and Educational Adventure, to address learning about the Philippine -Spanish Revolution among Grade 6 students of Pulung Santol Elementary School. The researcher employed the…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______

### Data Analytics (Cluster 7) — 6 theses

**Cluster ID:** 7 · **Size badge:** EMERGING · **Leading TF-IDF terms:** algorithm, data, data analytics, analytics, similarity, semantic

The name is an **unverified suggestion**. For each thesis, mark whether its research subject fits this group name. Check the source document if stored metadata looks wrong.

- **Thesix: Centralized Web-Based Capstone And Thesis Repository With Bert-Driven Semantic Similarity Algorithm** ([open thesis](http://localhost:5173/repository/667fe89e-c714-484f-aaaa-7e09b0557e6c); UUID `667fe89e-c714-484f-aaaa-7e09b0557e6c`)
  - Stored keywords: BERT, Capstone Repository, Semantic Similarity, Academic Innovation
  - Abstract evidence: The increasing volume of capstone and thesis projects in academic institutions necessitates a centralized and accessible repository to streamline management, accessibility, and visibility. Addressing this need, THESIX: Centralized Web -Based Capstone and Thesis Repository with BERT -Driven Semantic…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **ALUMNI PORTAL TRACKER WITH DATA ANALYTICS USING FOLD-GROWTH ALGORITHM** ([open thesis](http://localhost:5173/repository/ab97a031-f6b2-44e6-9a7e-6abcab04c809); UUID `ab97a031-f6b2-44e6-9a7e-6abcab04c809`)
  - Stored keywords: alumni portal, tracker, data analytics, fold-growth, algorithm, web based
  - Abstract evidence: Alumni Portal Tracker with Data Analytics using Fold-Growth Algorithm is a web-based Alumni Portal Tracker that enables the Don Honorio Ventura State University College of Computing Studies department in keeping and managing alumni records. It will serve as a useful interface for alumni and the d…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **E-pangasiwa: Data Dashboard for Business Establishment Monitoring for the Office of Municipal Treasury of the Municipality of Bacolor, Pampanga** ([open thesis](http://localhost:5173/repository/7ab3577d-8bf4-4a3d-b329-2d4852eb481a); UUID `7ab3577d-8bf4-4a3d-b329-2d4852eb481a`)
  - Stored keywords: track, monitor, data, dashboard, municipal treasury
  - Abstract evidence: A web-based data dashboard developed via Rapid Application Development (RAD) to modernize business establishment monitoring, permit applications, and tax revenue tracking for the Office of Municipal Treasury of Bacolor, Pampanga. The platform replaces paper records with interactive visual charts…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **Web-Based Qualifying Examination for Accountancy Students of Don Honorio Ventura State University – Main Campus** ([open thesis](http://localhost:5173/repository/11fdc7b9-4308-4e65-ac11-b57be86f8550); UUID `11fdc7b9-4308-4e65-ac11-b57be86f8550`)
  - Stored keywords: paper-based examination, web-based qualifying examination, digitized, database, data records, user-friendly, graphic user interface
  - Abstract evidence: Designed for the College of Business Studies at DHVSU Main Campus, this web-based examination platform digitizes the annual qualifying assessment for Bachelor of Science in Accountancy students. Developed using ASP.NET, SQL Server, and an Agile framework, the system replaces paper-based…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **Web-Based Grading System With Data Analytics For The Modernized Processing Of President’s And Dean’s Lists Candidates** ([open thesis](http://localhost:5173/repository/a634c87e-abe4-486c-b9d7-29f6fa9585a8); UUID `a634c87e-abe4-486c-b9d7-29f6fa9585a8`)
  - Stored keywords: web-based system, data analytics, manual processing, grade verification, Optical Character Recognition (OCR)
  - Abstract evidence: This study addresses the inefficiencies of the manual processing of President’s List (PL) and Dean’s List (DL) applications at Pampanga State University, which is time-consuming and prone to delays. A web-based system was developed to streamline registration, grade computation, verification,…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **My Honorian Buddy: A Web-Based Peer-Tutoring System For The Students Of Pampanga State University** ([open thesis](http://localhost:5173/repository/2784252f-6995-4ce5-be72-87dd0d1276f1); UUID `2784252f-6995-4ce5-be72-87dd0d1276f1`)
  - Stored keywords: peer-tutoring, web-based, content-based algorithm
  - Abstract evidence: The increasing integration of technology in education has amplified the need for personalized academic support, particularly in online learning environments. My Honorian Buddy is a web-based peer-tutoring system that connects students one-onone with suitable peer tutors using a content -based…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______

### Web-Based Systems (Cluster 8) — 5 theses

**Cluster ID:** 8 · **Size badge:** EMERGING · **Leading TF-IDF terms:** tracking, cashless, vaccination, interaction, assistive, management

The name is an **unverified suggestion**. For each thesis, mark whether its research subject fits this group name. Check the source document if stored metadata looks wrong.

- **Sabiyahe: A Cashless Mobile-Based E-Jeepney Tracking And Seat Reservation System** ([open thesis](http://localhost:5173/repository/6486a500-ce43-45fb-9d9f-2e539fc86d41); UUID `6486a500-ce43-45fb-9d9f-2e539fc86d41`)
  - Stored keywords: E-Jeepney Tracking System, Seat Reservation, Cashless Payment
  - Abstract evidence: SaBiyahe: A mobile-based application is a system created for public commuting. Aims at easing the problem that is still occurring with the manual onboarding system of public utility jeepneys and vehicles (PUJ, PUV). With the use of the said system application commuters may engage boarding and E…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **MSWD Online Financial Assistance Program Management System with SMS Notification and Status Tracking** ([open thesis](http://localhost:5173/repository/334eaf14-be5d-45a7-a8d2-5194f924bcf8); UUID `334eaf14-be5d-45a7-a8d2-5194f924bcf8`)
  - Stored keywords: MSWD, Online Financial Assistance, AICS, SMS, OTP, Status Tracking
  - Abstract evidence: A web-based application designed for the Municipal Social Welfare and Development Office (MSWDO) in Santo Tomas, Pampanga to digitize the Assistance to Individuals in Crisis Situations (AICS) program. Developed using an iterative methodology connecting the MSWDO, Budget, Accounting, and Treasury…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
  - **Source check:** Source caveat: the manuscript prints an HTEFinder/OJT abstract under its ABSTRACT heading; review that source mismatch before relying on the abstract for grouping.
- **VAXTRACK: A WEB APPLICATION FOR RABIES VACCINATION TRACKING AND MANAGEMENT** ([open thesis](http://localhost:5173/repository/2db3a8d8-cf98-4f9e-bcb6-6f4390e069dd); UUID `2db3a8d8-cf98-4f9e-bcb6-6f4390e069dd`)
  - Stored keywords: Web Application, Animal bites, Public Health Concern, Vaccination Tracking and Management, VaxTrack, User-friendly, Accessible, Manage Animal Welfare Information, Rabies Prevention
  - Abstract evidence: A web-based rabies surveillance and pet immunization tracking application developed for local government health staff and barangay officials in the City of San Fernando, Pampanga. Developed using the Waterfall SDLC model, the platform digitizes rabies case reporting, multi-pet registration,…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **SINDALAN CONNECT: A NEXT GENERATION LOCAL COMMUNITY MANAGEMENT SYSTEM POWERED BY AI CHATBOT AND EMERGENCY RESPONSE** ([open thesis](http://localhost:5173/repository/7203d29b-4dba-4ede-aa25-335ef85707a5); UUID `7203d29b-4dba-4ede-aa25-335ef85707a5`)
  - Stored keywords: Barangay Information System, E-Governance, Digital Public Services, Emergency Response System, AI Chatbot, Incident Reporting, Online Permit Application, Rural Health Unit Announcements, Community Engagement
  - Abstract evidence: As people today expect faster, more convenient, and more responsive public services, the system brings together modern digital tools to improve how the barangay works and how it engages with the community. Sindalan Connect automates essential services like online permit applications, certificate…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **Headlink: An Iot-Powered Head Pose Tracking System For Assistive Input And Human-Computer Interaction** ([open thesis](http://localhost:5173/repository/1bb71d5b-494c-452b-89e3-28ecafd4a81a); UUID `1bb71d5b-494c-452b-89e3-28ecafd4a81a`)
  - Stored keywords: Head Pose Tracking, Assistive Technologies, Human-Computer Interaction, Gesture-Based Inputs, Raspberry Pi, IoT System
  - Abstract evidence: HeadLink is an IoT-Powered Head Pose tracking system designed to make computers more accessible by providing a hands-free alternative for human-computer interaction. It uses computer vision and facial landmarking to track head position and translate it into mouse movements and functions. HeadLink…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______

### Web-Based Systems (Cluster 1) — 4 theses

**Cluster ID:** 1 · **Size badge:** EMERGING · **Leading TF-IDF terms:** monitoring, training, equipment, agile software, gps, operations

The name is an **unverified suggestion**. For each thesis, mark whether its research subject fits this group name. Check the source document if stored metadata looks wrong.

- **APPOKO: A Web-Based Elderly Medication Monitoring System with Descriptive Analytics and GPS Tracking** ([open thesis](http://localhost:5173/repository/8fbe4f92-7420-477e-a16d-084927644b9c); UUID `8fbe4f92-7420-477e-a16d-084927644b9c`)
  - Stored keywords: Elderly healthcare management, web-based system, GPS tracking, Agile Software Development Methodology, Web-based Approach
  - Abstract evidence: The elderly care facility at Bahay Pag-ibig in Telabastagan, San Fernando, Pampanga, struggled to monitor residents and track medication due to a high resident-to-staff ratio, leaving administrators and caregivers unable to maintain healthcare management effectively with the limited workforce…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **SISTEMA de OBRA: TRAINING MONITORING SYSTEM** ([open thesis](http://localhost:5173/repository/53601b50-dde7-42bc-b1c2-a417a3f57cb3); UUID `53601b50-dde7-42bc-b1c2-a417a3f57cb3`)
  - Stored keywords: Sistema de Obra, Training Monitoring System, Agile Software, ISO, Web-Based Approach
  - Abstract evidence: Developed for the Municipal Social Welfare and Development Office (MSWDO) of Bacolor, Pampanga, Sistema de Obra is a web-based training monitoring and management platform designed to replace outdated paper and spreadsheet systems. Built through Agile software development, the platform streamlines…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **Web-Based Equipment Maintenance Monitoring System for DHVSU Facilities** ([open thesis](http://localhost:5173/repository/e5aac843-a9ed-4be6-a45e-64f29da466d8); UUID `e5aac843-a9ed-4be6-a45e-64f29da466d8`)
  - Stored keywords: QR code generator, QR scanner, Equipment requests
  - Abstract evidence: A web-based equipment maintenance monitoring and inventory system developed for the Procurement and Supply Management Office (PSMO) and facility custodians at Don Honorio Ventura State University. Utilizing Agile development and the Kanban framework with Laravel and MySQL, the system replaces…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **iSecure: An Integrated Web-Based System for Base Access and Security Operations** ([open thesis](http://localhost:5173/repository/a23823a2-bda9-4a96-9ed4-085d0a24b6e7); UUID `a23823a2-bda9-4a96-9ed4-085d0a24b6e7`)
  - Stored keywords: iSecure, Access Control, RFID, Facial Recognition, OCR, Security Operations, ISO/IEC 25010, Agile Scrum
  - Abstract evidence: In areas that needs high security people often use outdated paper-based systems to track and archive record. This can, in turn, run into problems due to human error and inefficiencies. The goal of this project was to develop a web-based system named iSecure that automates security procedures in…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______

### Health Informatics — 4 theses

**Cluster ID:** 3 · **Size badge:** EMERGING · **Leading TF-IDF terms:** market, supply, medical, online market, android, farmers

The name is an **unverified suggestion**. For each thesis, mark whether its research subject fits this group name. Check the source document if stored metadata looks wrong.

- **ARADA: AN ANDROID ONLINE MARKET WITH SUPPLY- DEMAND STATISTICS FOR SELECTED LOCAL FARMERS AND SUPPLIERS IN PAMPANGA** ([open thesis](http://localhost:5173/repository/9ae051ee-b6b5-4df2-9d03-876f594045f9); UUID `9ae051ee-b6b5-4df2-9d03-876f594045f9`)
  - Stored keywords: Farmer‟s Market, Supply -Demand Statistics, Public Market, Android Application, CoVid-19
  - Abstract evidence: Agriculture is vital to the Philippines' economy where it is among the nation’s major industries. On the other hand, Pampanga is a province where one of its main industries is agriculture. Most farmers’ selling locations are in local markets. However, due to Covid-19, travel restrictions were…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **MedicScale: An Android Application for Patients’ Medical Chart** ([open thesis](http://localhost:5173/repository/57f8a9ca-b067-48b0-9c13-9eed8047f355); UUID `57f8a9ca-b067-48b0-9c13-9eed8047f355`)
  - Stored keywords: Medical, Record System, Electronic, Application, Hospital
  - Abstract evidence: MedicScale is an electronic medical record made to become a healthcare worker’s assistant. It is a mobile-based application that allows them to store and manage patients’ information and medical history. It will serve as the nurses’ companion whenever they do their rounds along with their…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **PALE-NGKIHAN: ONLINE MARKET SYSTEM FOR ARAYAT RICE TRADERS** ([open thesis](http://localhost:5173/repository/9ade9f3c-ffde-4481-be98-b2605cc3abf1); UUID `9ade9f3c-ffde-4481-be98-b2605cc3abf1`)
  - Stored keywords: online market system, web-based, agricultural, rice trading, middlemen
  - Abstract evidence: A web-based e-commerce platform designed to establish a direct trading channel between rice farmers and buyers in Arayat, Pampanga. Developed using Agile methodology, the system eliminates price disparities caused by intermediaries by providing transparent pricing, product cataloging, order…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **ANIDELIVERY: A FARMERS PLATFORM FOR SUSTAINABLE AGRICULTURE THROUGH MACHINE LEARNING-POWERED DIGITAL MARKETPLACE IN PAMPANGA** ([open thesis](http://localhost:5173/repository/143fb188-2e1a-41f9-8400-ca42466fd8a3); UUID `143fb188-2e1a-41f9-8400-ca42466fd8a3`)
  - Stored keywords: AniDelivery, Digital Marketplace, Supply Chain Management, Over Supply, Under Supply, Consumer
  - Abstract evidence: A mobile and web-based digital marketplace created to support sustainable agriculture in Pampanga by facilitating direct transactions between farmers and consumers. Developed using an Agile Scrum methodology, the platform incorporates machine learning algorithms for sales forecasting to mitigate…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______

### Data Analytics (Cluster 4) — 4 theses

**Cluster ID:** 4 · **Size badge:** EMERGING · **Leading TF-IDF terms:** virtual, learning, agile, visualization, programming, education

The name is an **unverified suggestion**. For each thesis, mark whether its research subject fits this group name. Check the source document if stored metadata looks wrong.

- **CODEQUEST: WHEN JAVA PROGRAMMING MEETS PLAYFUL LEARNING** ([open thesis](http://localhost:5173/repository/3970223e-18b9-45df-88a2-99a83abdee02); UUID `3970223e-18b9-45df-88a2-99a83abdee02`)
  - Stored keywords: Gamification, Blended, Engagement, Effectiveness
  - Abstract evidence: CodeQuest is an interactive, web-based 3D gamified educational platform developed to enhance Java programming instruction through a blended learning approach. Developed using React.js, Three.js, Node.js, and PostgreSQL under the Agile Scrum framework, the system integrates quest-based programming…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **ChemLab AR: AUGMENTED REALITY-BASED CHEMISTRY EXPERIMENTS** ([open thesis](http://localhost:5173/repository/e2d47493-770e-4d2a-bf73-c6c191258fe0); UUID `e2d47493-770e-4d2a-bf73-c6c191258fe0`)
  - Stored keywords: Augmented Reality (AR), Ball-and-Stick Models, Chemical Reaction, Chemistry Education, Molecular Geometry, Mobile Application, Virtual Laboratory, 3D Visualization
  - Abstract evidence: The lack of sufficient laboratory equipment in Philippine public schools significantly hinders the effective learning of general chemistry concepts such as molecular structures and chemical reactions. To take aim at this educational gap, the "ChemLab AR" Android mobile application was developed,…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **CyberDefender: A Game-Based Learning Platform for Enhancing Students' Cyber Threat Awareness** ([open thesis](http://localhost:5173/repository/10416ed7-4445-456d-9c4c-c9504765e40f); UUID `10416ed7-4445-456d-9c4c-c9504765e40f`)
  - Stored keywords: Cybersecurity, Roblox, Agile, ISO 25010
  - Abstract evidence: The educational game CyberDefender was developed with the aim of helping to solve the growing cybersecurity awareness problems among students, through the use of interactive game-based learning. This means finding innovative ways to increase their knowledge about the risk of cyber threats, which i…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **ARAL: An Android-based 3D Virtual Learning Material for Preschool Students** ([open thesis](http://localhost:5173/repository/a5d4a3d3-378c-4f59-b6f0-b3144cbc52e4); UUID `a5d4a3d3-378c-4f59-b6f0-b3144cbc52e4`)
  - Stored keywords: 3D, Android, C-sharp (C#), Platform, Unity3D, Virtual Learning Environment (V.L.E), Structured Query Language (SQL), Windows, XAMPP
  - Abstract evidence: The A.R.A.L. an Android-based 3D Virtual Learning Material for Preschool Students is a 3D Virtual and interactive learning material for visual presentation of alphabets, shapes, colors, and numbers. The study was proven an effective teaching aid for teachers and to use the 3D virtual learning…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______

### Internet of Things — 4 theses

**Cluster ID:** 6 · **Size badge:** EMERGING · **Leading TF-IDF terms:** smart, irrigation, water, iot, monitoring, things

The name is an **unverified suggestion**. For each thesis, mark whether its research subject fits this group name. Check the source document if stored metadata looks wrong.

- **ANTABE: AN INTELLIGENT GUIDE STICK FOR VISUALLY IMPAIRED** ([open thesis](http://localhost:5173/repository/b05abf84-2643-4d03-888b-80fdb187152d); UUID `b05abf84-2643-4d03-888b-80fdb187152d`)
  - Stored keywords: Visual Impairment, Smart Cane, Assistive Technology, Iot
  - Abstract evidence: Antabe is an intelligent assistive guide stick designed to enhance spatial awareness, obstacle avoidance, and independent mobility for visually impaired individuals in Guagua, Pampanga. Powered by an Arduino microcontroller, the device integrates ultrasonic sensors for multi-directional obstacle…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **AQUAFLOW: AN ARDUINO-POWERED SMART IRRIGATION SYSTEM FOR GUMAIN DAM** ([open thesis](http://localhost:5173/repository/22f74b8e-7c13-4714-bab3-67e10140965d); UUID `22f74b8e-7c13-4714-bab3-67e10140965d`)
  - Stored keywords: Smart Irrigation System, Arduino Technology, Blynk Application, IoT (Internet of Things), Water Flow Control, Water Level Monitoring
  - Abstract evidence: AquaFlow is an IoT-based automated irrigation system developed for agricultural fields connected to Gumain Dam in Floridablanca, Pampanga to reduce water wastage and prevent crop damage from overwatering or drought stress. Built through Rapid Application Development (RAD), the system integrates a…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **ShopEase: AN IOT-BASED SHOPPING CART WITH BARCODE SCANNER AND REAL-TIME MULTI-CART MONITORING SYSTEM** ([open thesis](http://localhost:5173/repository/3ee906b3-2e8d-4da9-b155-5a70c69ba4fa); UUID `3ee906b3-2e8d-4da9-b155-5a70c69ba4fa`)
  - Stored keywords: IoT (Internet of Things), Real-Time Monitoring, Multiple Carts, Cashier Application
  - Abstract evidence: Traditional supermarket checkout methods create significant friction for customers, often resulting in long queues and reduced operational efficiency. To resolve these challenges, this study developed ShopEase: An IoT-Based Shopping Cart with Barcode Scann er and Real-Time Multi-Cart Monitoring…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **AnImo: An AI-Driven Agricultural Hybrid Platform with Intelligent Crop Recommendations and IoT-Enabled Solar-Powered Water Irrigation Based on Soil Analysis** ([open thesis](http://localhost:5173/repository/b1f3b63d-16ce-4458-8224-163564b61a8a); UUID `b1f3b63d-16ce-4458-8224-163564b61a8a`)
  - Stored keywords: Gemini, Internet of Things, Smart Farming, Solar -Powered Water Pump, Soil Analysis
  - Abstract evidence: Local farmers in the Philippines face significant challenges, including fluctuating market prices, soil degradation, and climate variability, which contribute to low productivity and economic losses. Addressing the urgent need for innovative technological solutions, this project developed AnImo: An…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______

### Aeroponics — 4 theses

**Cluster ID:** 9 · **Size badge:** EMERGING · **Leading TF-IDF terms:** logic, fuzzy, fuzzy logic, topic, trend, analysis

The name is an **unverified suggestion**. For each thesis, mark whether its research subject fits this group name. Check the source document if stored metadata looks wrong.

- **THESYS+: A Semantic-Based Thesis Retrieval and Topic Trend Analysis System for CCS Undergraduate Theses at Pampanga State University** ([open thesis](http://localhost:5173/repository/dfd4a0cd-482f-4ad4-bb67-a8d356655640); UUID `dfd4a0cd-482f-4ad4-bb67-a8d356655640`)
  - Stored keywords: none
  - Abstract evidence: Traditional academic repositories rely on keyword-based searches, making it difficult to detect semantic topic redundancies or track research trajectories over time. To address this, THESYS+ was developed as an intelligent thesis retrieval and topic trend analysis platform for the College of…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
  - **Source check:** No stored keywords; inspect the source if this affects the topic.
- **Career Track Mobile Application Using Fuzzy Logic For High School Student** ([open thesis](http://localhost:5173/repository/a7e917cd-448a-46ab-8f69-d4d798f4865b); UUID `a7e917cd-448a-46ab-8f69-d4d798f4865b`)
  - Stored keywords: Holland Codes, Fuzzy Logic
  - Abstract evidence: The K to 12 programs include kindergarten through 12th grade, allowing students to acquire ideas and skills, develop lifelong learners, and prepare graduates for higher education, middle-level skill development, employment, and entrepreneurship. During the kindergarten -to-high school program,…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **SIMULATION OF LOGIC GATES CIRCUITS TEST AND GUIDE USING ANDROID APPLICATION** ([open thesis](http://localhost:5173/repository/7912270e-6a1b-4cb8-baa7-16ac04b6df6a); UUID `7912270e-6a1b-4cb8-baa7-16ac04b6df6a`)
  - Stored keywords: Logic gates, simulator, application
  - Abstract evidence: Educational software is becoming increasingly significant in schools and colleges. In keeping with this trend, educational institutions are increasingly relying on mobile applications to help them develop, particularly in teaching and learning. The proponents of Logic Gate Operations have…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **A FUZZY LOGIC-BASED MOBILE APPLICATION FOR REAL-TIME MONITORING OF MODULAR INDOOR FARMING** ([open thesis](http://localhost:5173/repository/8212ab33-5c0e-4b1f-8383-583f1db45722); UUID `8212ab33-5c0e-4b1f-8383-583f1db45722`)
  - Stored keywords: Aeroponics, fuzzy logic algorithm, indoor
  - Abstract evidence: An automated indoor aeroponics system and mobile application developed to monitor and manage crucial plant environmental parameters, including temperature, humidity, pH, and water levels. Developed using a Waterfall model for the mobile app and a prototype model for the tower hardware, the system…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______

### Natural Language Processing — 4 theses

**Cluster ID:** 11 · **Size badge:** EMERGING · **Leading TF-IDF terms:** health, complaint, language processing, natural, natural language, communication

The name is an **unverified suggestion**. For each thesis, mark whether its research subject fits this group name. Check the source document if stored metadata looks wrong.

- **EXTHEALTH: A BROWSER EXTENSION FOR HEALTH INFORMATION ON X USING NATURAL LANGUAGE PROCESSING (NLP)** ([open thesis](http://localhost:5173/repository/8069344d-5287-40de-8e51-176fb13b8d2a); UUID `8069344d-5287-40de-8e51-176fb13b8d2a`)
  - Stored keywords: Health Misinformation, Browser Extension, Fact-checking, X, Twitter, Social Media
  - Abstract evidence: Many social media users lack the time or motivation to fact-check health-related claims they encounter online, allowing health misinformation to spread widely on platforms such as X (formerly Twitter). This study presents eXtHealth, a browser extension that uses Natural Language Processing (NLP) to…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **#31B: A 117 Emergency Communication Platform For Abuse Report In A Mobile Application** ([open thesis](http://localhost:5173/repository/b34020a4-99ff-4087-a7f8-09b9690e4063); UUID `b34020a4-99ff-4087-a7f8-09b9690e4063`)
  - Stored keywords: Domestic Abuse, Complaint, Mobile Application, VAWC
  - Abstract evidence: The proposed study aims to establish an idea of a free communication platform for the victims of abuse, that is user-friendly, with much better assistance and immediate response, with the help and support from the local authorities and social services. It would also be a big help to promote…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **DHVCHAT: A WEB-BASED INTELLIGENT CHAT ASSISTANT FOR THE ADMISSIONS OFFICE USING NATURAL LANGUAGE PROCESSING** ([open thesis](http://localhost:5173/repository/18737b6e-983a-4ae6-915a-8f155aefb160); UUID `18737b6e-983a-4ae6-915a-8f155aefb160`)
  - Stored keywords: Natural Language Processing, chatbots, university admission, AI-enhanced communication systems
  - Abstract evidence: DHVChat is an AI-powered conversational web assistant created for the Admissions Office of Don Honorio Ventura State University to automate student inquiry handling. Built using ReactJS, Python, and OpenAI's GPT-3.5 Turbo text embeddings within an iterative waterfall methodology, the system…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **Barangaymed+: A Hybrid Application With Inventory And Healthcare Service System For Barangay Health Centers In Municipality Of Floridablanca, Pampanga** ([open thesis](http://localhost:5173/repository/942ded1d-9463-40d0-bdff-796f6add7f1d); UUID `942ded1d-9463-40d0-bdff-796f6add7f1d`)
  - Stored keywords: BarangayMed+, digital health, teleconsultation, inventory management, healthcare system, ISO/IEC 25010, barangay health centers
  - Abstract evidence: Barangay health centers serve as the primary access point for basic healthcare in the Philippines, yet many continue to depend on manual processes that result in long queues, inefficient record handling, delayed access to medicines, and limited communication with residents. This study developed…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______

### Active Aging — 3 theses

**Cluster ID:** 10 · **Size badge:** EMERGING · **Leading TF-IDF terms:** matching, employment, dormitory, senior, attachments, ai-powered

The name is an **unverified suggestion**. For each thesis, mark whether its research subject fits this group name. Check the source document if stored metadata looks wrong.

- **Rehirely: A Mobile-Based Application For Job-matching For Senior Citizen Employment** ([open thesis](http://localhost:5173/repository/c7d80880-8132-4163-b6fb-4ae63573e4ca); UUID `c7d80880-8132-4163-b6fb-4ae63573e4ca`)
  - Stored keywords: mobile application, job matching, digital inclusion, active aging, age - inclusive employment, employment technology, user-centered design, RAD methodology, ISO/IEC 25010
  - Abstract evidence: REHIRELY is a mobile -based job-matching application developed to help senior citizens aged 60 and above in Pampanga access local employment opportunities through a secure and user -friendly digital platform. The system was designed to address challenges such as digital exclusion and age-related…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **Attachmates: A Dating App For Ai-Powered Compatibility-Based Matching Through Attachments Styles And Love Languages** ([open thesis](http://localhost:5173/repository/c1b8c2f6-69c3-47f6-80cb-ecaa3fb79c1c); UUID `c1b8c2f6-69c3-47f6-80cb-ecaa3fb79c1c`)
  - Stored keywords: attachment styles, love languages, dating fatigue, hybrid recommendation system, psychology-based matching, Flutter, Firebase, AI matching
  - Abstract evidence: Many dating applications today prioritize physical appearance and fast interactions, often leading to emotional mismatches, inconsistent connections, and dating fatigue among users. This study focused on development of AttachMates, a dating application designed to improve compatibility by…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **DormHonorio: DORMITORY BOOKING AND ALGORITHM-DRIVEN ROOMMATE MATCHING MOBILE APPLICATION FOR HONORIANS** ([open thesis](http://localhost:5173/repository/7aa5c31d-8be0-4e1b-b4aa-1b6a87bb016c); UUID `7aa5c31d-8be0-4e1b-b4aa-1b6a87bb016c`)
  - Stored keywords: weighted scoring algorithm, roommate matching, dormitory, tenant
  - Abstract evidence: The goal of this study was to develop DormHonorio, a mobile application that helps Pampanga State University students find dormitories and compatible roommates in a more organized and reliable way. Since there is still no official online platform for this purpose, students often experience a…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______

### Web-Based Systems (Cluster 12) — 2 theses

**Cluster ID:** 12 · **Size badge:** UNDEREXPLORED · **Leading TF-IDF terms:** geofencing, geofencing technology, technology, training, management, utilizing

The name is an **unverified suggestion**. For each thesis, mark whether its research subject fits this group name. Check the source document if stored metadata looks wrong.

- **DORMIFY: DORM FINDER AND MANAGEMENT SYSTEM WITH GEOFENCING TECHNOLOGY FOR DHVSU MAIN CAMPUS** ([open thesis](http://localhost:5173/repository/827a721c-0ecc-4896-b9b4-f5571f32736c); UUID `827a721c-0ecc-4896-b9b4-f5571f32736c`)
  - Stored keywords: Dorm Finder, Management System, Geofencing Technology
  - Abstract evidence: Dormify is an Android-based dormitory finder and rental management system created for students, faculty, and property owners within a 1-kilometer radius of DHVSU Main Campus in Bacolor, Pampanga. Developed using an iterative model, the application incorporates Google Maps geofencing to display…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______
- **HTEFinder: A Web Application Utilizing Geofencing Technology** ([open thesis](http://localhost:5173/repository/ca211b67-2032-48e0-90d8-d30c250a7804); UUID `ca211b67-2032-48e0-90d8-d30c250a7804`)
  - Stored keywords: On-the-Job Training, Host Training Establishment, Geofencing Technology, Expert System, Laravel Framework, MySQL Database
  - Abstract evidence: HTEFinder is a web-based platform developed to streamline the search and placement process of Host Training Establishments (HTE) for on-the-job training (OJT) students in the College of Computing Studies at DHVSU. Developed with the Laravel framework and MySQL using an iterative approach, the…
  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______

## Full stored abstracts for source checking

### THESYS+: A Semantic-Based Thesis Retrieval and Topic Trend Analysis System for CCS Undergraduate Theses at Pampanga State University

UUID: `dfd4a0cd-482f-4ad4-bb67-a8d356655640` · [open thesis](http://localhost:5173/repository/dfd4a0cd-482f-4ad4-bb67-a8d356655640)

Stored keywords: none

Traditional academic repositories rely on keyword-based searches, making it difficult to detect semantic topic redundancies or track research trajectories over time. To address this, THESYS+ was developed as an intelligent thesis retrieval and topic trend analysis platform for the College of Computing Studies (CCS) at Pampanga State University. The system employs Sentence-BERT (SBERT) embeddings and cosine similarity for context-aware search and title duplicate detection, alongside TF-IDF and clustering algorithms for research trend visualization across the 2023–2025 academic years. Furthermore, THESYS+ incorporates an Optical Character Recognition (OCR) pipeline to verify student credential documents during registration. Evaluated using a benchmarked corpus of 105 CCS undergraduate theses, the system achieved high precision in detecting semantically similar titles (&gt;0.90 similarity score), streamlining literature retrieval and preventing redundant departmental research.

**Source check:** No stored keywords; inspect the source if this affects the topic.

### Thesix: Centralized Web-Based Capstone And Thesis Repository With Bert-Driven Semantic Similarity Algorithm

UUID: `667fe89e-c714-484f-aaaa-7e09b0557e6c` · [open thesis](http://localhost:5173/repository/667fe89e-c714-484f-aaaa-7e09b0557e6c)

Stored keywords: BERT, Capstone Repository, Semantic Similarity, Academic Innovation

The increasing volume of capstone and thesis projects in academic institutions necessitates a centralized and accessible repository to streamline management, accessibility, and visibility. Addressing this need, THESIX: Centralized Web -Based Capstone and Thesis Repository with BERT -Driven Semantic Similarity Algorithm was developed for the College of Computing Studies at Don Honorio Ventura State University. The system integrates a web -based platform with a simila rity detection feature powered by Bidirectional Encoder Representations from Transformers (BERT), enabling users to upload, search, and analyze capstone and thesis projects efficiently. The study utilized an iterative software development methodology, incorporating user feedback at every stage to ensure alignment with user needs. Surveys and quantitative analysis were conducted to evaluate the challenges faced by students and faculty, guiding the design of the platform's features. Key functionalities include a personalized archive, advanced search capabilities, descriptive analytics, and a similarity checker to enhance research efficiency and prevent redundancy. Preliminary testing demonstrated the system's effectiveness in improving accessibility, enhancing search accuracy, and promoting academic integrity. Descriptive analytics further enables trend identification, aiding in innovative research topic exploratio n. Evaluations using ISO 25010 criteria highlighted the system’s functionality, usability, and reliability confirming its potential to revolutionize manuscript management for CCS researchers.

### Hubisko: Scholarship Management In Pampanga Through Centralized Automation

UUID: `4d01b7a0-e453-43de-b900-8b84c41d6f70` · [open thesis](http://localhost:5173/repository/4d01b7a0-e453-43de-b900-8b84c41d6f70)

Stored keywords: Web Based Automation System, Scholarship

Scholarship application and management in the Philippines, particularly within Pampanga, remains largely dependent on manual and paper-based processes, creating inefficiencies for both student applicants and scholarship providers and making it difficult to keep scholarship-related information accurate and accessible. This study developed HubIsko, a centralized web-based automation system designed to streamline the scholarship application and management process for the College of Computing Studies at Don Honorio Ventura State University, allowing student applicants to create accounts, browse and apply for available scholarships, track application status, submit required documents, and receive real-time notifications, while giving scholarship providers tools to post and manage programs, review applications, generate reports, and communicate with applicants through an integrated forum feature. The system was evaluated through alpha testing with IT experts and beta testing with 68 end users against ISO 25010 quality criteria — functional suitability, performance efficiency, compatibility, reliability, security, and maintainability — with both phases showing strong to outstanding performance and users particularly praising the Google Login integration and cross-device usability, confirming that HubIsko offers a practical, centralized, and user-friendly solution that reduces inefficiencies in scholarship administration and improves communication and transparency between students and providers.

### APPOKO: A Web-Based Elderly Medication Monitoring System with Descriptive Analytics and GPS Tracking

UUID: `8fbe4f92-7420-477e-a16d-084927644b9c` · [open thesis](http://localhost:5173/repository/8fbe4f92-7420-477e-a16d-084927644b9c)

Stored keywords: Elderly healthcare management, web-based system, GPS tracking, Agile Software Development Methodology, Web-based Approach

The elderly care facility at Bahay Pag-ibig in Telabastagan, San Fernando, Pampanga, struggled to monitor residents and track medication due to a high resident-to-staff ratio, leaving administrators and caregivers unable to maintain healthcare management effectively with the limited workforce available. To address this, the study developed APPOKO, a web-based elderly medication monitoring system featuring descriptive analytics and GPS tracking, built using the Agile Software Development Methodology and informed by a mixed quantitative-qualitative research design that included semi-structured interviews with stakeholders. Beta testing evaluated the system across eight ISO 25010 quality dimensions — Functional Suitability (3.86), Performance Efficiency (3.9), Compatibility (3.85), Usability (3.91), Reliability (3.82), Security (4.0), Maintainability (3.98), and Portability (3.76) — yielding an overall average mean of 3.88, interpreted as acceptable and reflecting the effectiveness of the chosen methodology and data collection approach. These results confirm that APPOKO successfully addresses the limitations of the facility's outdated manual processes, offering an efficient, reliable, and modernized web-based alternative that streamlines stakeholder workflows and supports the broader shift toward digital elderly healthcare management.

### EXTHEALTH: A BROWSER EXTENSION FOR HEALTH INFORMATION ON X USING NATURAL LANGUAGE PROCESSING (NLP)

UUID: `8069344d-5287-40de-8e51-176fb13b8d2a` · [open thesis](http://localhost:5173/repository/8069344d-5287-40de-8e51-176fb13b8d2a)

Stored keywords: Health Misinformation, Browser Extension, Fact-checking, X, Twitter, Social Media

Many social media users lack the time or motivation to fact-check health-related claims they encounter online, allowing health misinformation to spread widely on platforms such as X (formerly Twitter). This study presents eXtHealth, a browser extension that uses Natural Language Processing (NLP) to detect and verify health-related posts on social media by surfacing supporting or opposing articles, while also delivering timely health reminders and tips to keep users informed. Developed through an iterative software development methodology to remain responsive to user feedback, the system was evaluated using a quantitative approach, with alpha testing conducted by health and IT professionals and beta testing carried out with X users selected through purposive sampling; the results yielded a weighted mean of 3.61, interpreted as "Strongly Agree," reflecting strong user satisfaction with the extension's usability. The findings confirm that eXtHealth reliably detects and verifies health-related content and provides valuable, accurate health information, positioning it as a practical tool to help users combat health misinformation and stay better informed on health topics.

### #31B: A 117 Emergency Communication Platform For Abuse Report In A Mobile Application

UUID: `b34020a4-99ff-4087-a7f8-09b9690e4063` · [open thesis](http://localhost:5173/repository/b34020a4-99ff-4087-a7f8-09b9690e4063)

Stored keywords: Domestic Abuse, Complaint, Mobile Application, VAWC

The proposed study aims to establish an idea of a free communication platform for the victims of abuse, that is user-friendly, with much better assistance and immediate response, with the help and support from the local authorities and social services. It would also be a big help to promote awareness to the local residents. Quantitative descriptive type of approach was used, which ser ved as a helpful way of reporting abuse cases through a mobile application, and also to gather data regarding the abuse cases in the target locale. The researchers used agile methodology to emphasize the collaboration of the group, user feedback, continuous improvement, and the adapting capacity to changing activity. Surveys were conducted to test the functional stability, reliability, usability, perf ormance efficiency and security of the study. The survey result showed th e difference between the proposed system and the existing system. It was found that the proposed system has a greater impact and advantage to the respondents with an average mean of 3.73 (Interpretation of Strongly Agree) compared to the existing system with an average mean of 2.52 (Interpretation of Agree). The result proved that the application was able to provide an additional way of submitting a complaint report to the authorities and useful information to the respondents in the community.

### ALUMNI PORTAL TRACKER WITH DATA ANALYTICS USING FOLD-GROWTH ALGORITHM

UUID: `ab97a031-f6b2-44e6-9a7e-6abcab04c809` · [open thesis](http://localhost:5173/repository/ab97a031-f6b2-44e6-9a7e-6abcab04c809)

Stored keywords: alumni portal, tracker, data analytics, fold-growth, algorithm, web based

Alumni Portal Tracker with Data Analytics using Fold-Growth Algorithm is a web-based Alumni Portal Tracker that enables the Don Honorio Ventura State University College of Computing Studies department in keeping and managing alumni records. It will serve as a useful interface for alumni and the d epartment to communicate and collaborate. Alumni can access information about their batch mates, as well as announcements, events, forums, and job postings. Moreover, alumni can use the system to update their information. The administrator can post announcements, events, forums, and print reports on the Administrator page. Employers can also advertise job openings on the alumni site by registering. Keyword/s: alumni portal, tracker, data analytics, fold-growth, algorithm, web based

### ARADA: AN ANDROID ONLINE MARKET WITH SUPPLY- DEMAND STATISTICS FOR SELECTED LOCAL FARMERS AND SUPPLIERS IN PAMPANGA

UUID: `9ae051ee-b6b5-4df2-9d03-876f594045f9` · [open thesis](http://localhost:5173/repository/9ae051ee-b6b5-4df2-9d03-876f594045f9)

Stored keywords: Farmer‟s Market, Supply -Demand Statistics, Public Market, Android Application, CoVid-19

Agriculture is vital to the Philippines' economy where it is among the nation’s major industries. On the other hand, Pampanga is a province where one of its main industries is agriculture. Most farmers’ selling locations are in local markets. However, due to Covid-19, travel restrictions were implemented, interrupting the vegetable supply chain and causing hundreds of farmers' livelihoods to be affected negatively. The researchers came up with "Arada: An Android Online Market with Supply -Demand Statistics for Selected Local Farmers and Suppliers in Pampanga" an agricultural platform for the households, farmers, and suppliers to buy and sell their products. This platform has in -app statistics where the users can see the demand and supply of the products. This allows the farmers and suppliers to sell herbs, vegetables, fruits, and dairy products to nearby residents online. This application includes the following features: Product listing, search bar, rating system, add -to-cart, payment options, delivery options, and chat system. The researchers used a survey questionnaire to determine their level of agreement with the given scenarios using a four-point Likert Scale where 1 stand for strongly disagree and 4 stands for strongly agree The results of the survey questionnaire showed that the majority of the 384 respondents meet the minimum requirements of the application The respondents’ willingness, ease of access, comfortability, sense of security, reliability, and satisfaction were also recorded where the majority of the respondents agreed.

### Career Track Mobile Application Using Fuzzy Logic For High School Student

UUID: `a7e917cd-448a-46ab-8f69-d4d798f4865b` · [open thesis](http://localhost:5173/repository/a7e917cd-448a-46ab-8f69-d4d798f4865b)

Stored keywords: Holland Codes, Fuzzy Logic

The K to 12 programs include kindergarten through 12th grade, allowing students to acquire ideas and skills, develop lifelong learners, and prepare graduates for higher education, middle-level skill development, employment, and entrepreneurship. During the kindergarten -to-high school program, there was not enough consultation with parents, teachers, especially students. To solve this problem, the proponent wanted to devel op an Android -based mobile application. Career Track Mobile Application using Fuzzy Logic for High School Students was a simple educational tool that could be used to determine the strand. It provides a batch of strand -related questions and self -assessment adapted from holland codes. The study offers reliable results that were processed using the Fuzzy Logic. The research utilized the experimental research design. The researcher used the software development life cycle (SDLC), as represented by Rapid Agile development, to represent the development process for the study. The primary goal of the research was to helped the high school student chose their strand based on their knowledge, personality, skills, and interest in an efficient and accessible way. This helped the student to boost their knowledge and confidence in choosing their future career path. The mobile application was convenient and easy to access for the students who liked to determine their suitable strand. The students found it simple to determine what strand was capable of their knowledge, personality, skills, and interest. As a result, the respondents found that the mobile application was functional, usable, reliable, efficient, and portable.

### E-pangasiwa: Data Dashboard for Business Establishment Monitoring for the Office of Municipal Treasury of the Municipality of Bacolor, Pampanga

UUID: `7ab3577d-8bf4-4a3d-b329-2d4852eb481a` · [open thesis](http://localhost:5173/repository/7ab3577d-8bf4-4a3d-b329-2d4852eb481a)

Stored keywords: track, monitor, data, dashboard, municipal treasury

A web-based data dashboard developed via Rapid Application Development (RAD) to modernize business establishment monitoring, permit applications, and tax revenue tracking for the Office of Municipal Treasury of Bacolor, Pampanga. The platform replaces paper records with interactive visual charts and automated SMS/email alerts, earning an overall functionality rating of 3.94 under ISO 9126-1.

### KlasikoPinas: Filipino Traditions and Mythical Creatures Digital Game

UUID: `fc64acbe-4a43-4d27-bb0f-76fb7e279caf` · [open thesis](http://localhost:5173/repository/fc64acbe-4a43-4d27-bb0f-76fb7e279caf)

Stored keywords: Filipino traditions, traditional games, mythical creatures, digital game, Godot engine, KlasikoPinas

A 2.5D educational game developed using the Godot Engine and Blender to preserve Filipino cultural identity by teaching traditional outdoor games and indigenous folklore. Built using an Agile Kanban workflow, the game translates traditional games like Palosebo, Sipa, Luksong Baka, and Langit Lupa into interactive levels, achieving an overall evaluation mean of 2.72 under ISO/IEC 25010.

### Mamalakaya: A Web-based HIV Awareness Campaign Site with an Educational Game and Testing Centers Directory

UUID: `d9078b46-77bb-425c-a996-524ae65b9f72` · [open thesis](http://localhost:5173/repository/d9078b46-77bb-425c-a996-524ae65b9f72)

Stored keywords: HIV, educational game, awareness, education, campaign

An automated public health campaign website designed to provide accessible HIV education, destigmatization resources, and healthcare linkage during the COVID-19 pandemic. Developed using Agile methodology, the platform provides multimedia instructional content, an interactive educational game, a national testing center directory, and appointment booking assistance, achieving an overall evaluation score of 4.27.

### MedicScale: An Android Application for Patients’ Medical Chart

UUID: `57f8a9ca-b067-48b0-9c13-9eed8047f355` · [open thesis](http://localhost:5173/repository/57f8a9ca-b067-48b0-9c13-9eed8047f355)

Stored keywords: Medical, Record System, Electronic, Application, Hospital

MedicScale is an electronic medical record made to become a healthcare worker’s assistant. It is a mobile-based application that allows them to store and manage patients’ information and medical history. It will serve as the nurses’ companion whenever they do their rounds along with their respective stations. Descriptive method together with agile software development was utilized throughout the creation of both the system and the manuscript. The system was designed to provide a digital way of storing patients’ records that allows the healthcare workers to assess them and put down the findings immediately together with the history. The primary purpose of providing them a work companion is to eliminate the redundancy of writing down patient’s information manually and transferring them into their respective stations using their outdated systems.

### MODEYUL: An Educational Kapampangan Supplemental Game App for Grade 3 Students

UUID: `f765b44b-073e-42d0-b453-f975d592d3dd` · [open thesis](http://localhost:5173/repository/f765b44b-073e-42d0-b453-f975d592d3dd)

Stored keywords: Programming, Unity Software, C#, 2D, Game App

Developed during the COVID-19 pandemic, ModeYul is an offline, module-based 2D educational Android game application designed to help Grade 3 students learn the Kapampangan language and local culture. Built using the Waterfall methodology with Unity and C#, the system incorporates interactive visuals, sounds, and mini-games to boost learning motivation and mother-tongue comprehension. Evaluations from 100 parents and guardians confirmed the application's learnability, efficiency, and effectiveness as an engaging supplemental learning tool.

### Sabiyahe: A Cashless Mobile-Based E-Jeepney Tracking And Seat Reservation System

UUID: `6486a500-ce43-45fb-9d9f-2e539fc86d41` · [open thesis](http://localhost:5173/repository/6486a500-ce43-45fb-9d9f-2e539fc86d41)

Stored keywords: E-Jeepney Tracking System, Seat Reservation, Cashless Payment

SaBiyahe: A mobile-based application is a system created for public commuting. Aims at easing the problem that is still occurring with the manual onboarding system of public utility jeepneys and vehicles (PUJ, PUV). With the use of the said system application commuters may engage boarding and E -jeepney hassle-free and without compromising IATF minimum health safety protocols amidst the COVID19 pandemic. The application has functions such, E-Jeepney Route Tracking and Mapping, Seat Reservation, Cashless Payment with OTP Generation, and Contact Tracing using QR Code. Keyword/s: E-Jeepney Tracking System, Seat Reservation, Cashless Payment.

### “Simplify!” Android-Based Application: Improving Students’ Productivity by Scheduling and Organizing Tasks of Students

UUID: `de7b079a-1e63-44ef-ad33-95b87a581174` · [open thesis](http://localhost:5173/repository/de7b079a-1e63-44ef-ad33-95b87a581174)

Stored keywords: time management, schedule, organize, tasks, productivity, students

The thesis study titled, —Simplify! Android -Based Application: Improving Students‟ Productivity by Scheduling and Organizing Tasks of Students is designed for students to properly manage their school tasks and use their time efficiently. The application assists students in organizing academic assignments as well as personal tasks. The application includes an alarm and calendar feature that allows the user to set the time and date when they want to begin working on their assignments while avoiding delaying tasks when the deadline approaches. When a user creates a task and feels demotivated, the application contains a keyword detection algorithm that can suggest relevant motivating quotations. The application can then be used to provide words of encouragement. Furthermore, the application includes a community booster, so that users can feel more engaged and connected with their peers. In developing the application, Agile Methodology is used as the System Development Life Cycle. Questionnaire distribution, FURPS (Functionality, Usability, Reliability, Performance and Supportability) evaluation of software attributes, book and online research are used to collect data for the study. To justify the need of the application, the proponents used a descriptive study method to analyse students' time management and school work routines. At the end of the study, the proponents found out that 45% of the respondents often delay their tasks and 60% of the respondents write down their tasks in a piece of paper which leads to disorganization of tasks, and the application received a very much acceptable 3.68 rating from system evaluators and 3.57 rating from IT experts.

### SIMULATION OF LOGIC GATES CIRCUITS TEST AND GUIDE USING ANDROID APPLICATION

UUID: `7912270e-6a1b-4cb8-baa7-16ac04b6df6a` · [open thesis](http://localhost:5173/repository/7912270e-6a1b-4cb8-baa7-16ac04b6df6a)

Stored keywords: Logic gates, simulator, application

Educational software is becoming increasingly significant in schools and colleges. In keeping with this trend, educational institutions are increasingly relying on mobile applications to help them develop, particularly in teaching and learning. The proponents of Logic Gate Operations have identified the concerns such as lack of material availability, pricing of the actual substantial, material durability. The pre -study survey was given to College of Computing Studies First Year Students and the findings were examined. The proponents used descriptive study method. Therefore, the proponents created —The Simulation of Logic Gate Circuits Test and Guide Using an Android Application‖ as an additional tool to aid students with their Logic Gate studies. Users will be able to witness the process, which will assist them to learn their subject matter. It has also simulation of gates interface for students to practice logic gates. RAD was used as methodology in developing the application and evaluated using the criteria in ISO25010. According to the beta test results the functionality of the mobi le application is 4.20 which is the highly acceptable, the usability is 4.20 which is the highly acceptable, the efficiency is 4.25 which is the highly acceptable and the maintainability is 4.24 which is highly acceptable, while in the alpha test results the functionality of the mobile application is 4.57 which is the highly acceptable, the usability is 4.66 which is the highly acceptable, the efficiency is 4.33 which is the highly acceptable and the maintainability is 4.00 which is acceptable.

### Vehicle Management System using Cloud Mapping Technology

UUID: `ad4f3076-3c4e-4f73-b54a-2b6f97c485e4` · [open thesis](http://localhost:5173/repository/ad4f3076-3c4e-4f73-b54a-2b6f97c485e4)

Stored keywords: cloud server, mapping

Due to pandemic, limited transportation led to decrease in overall economic status of a country. In the Philippines, where most of the transactions were traditional, the said transportation industries had to adapt to the current situation. Through the help of the internet and newest web technologies of today, especially the awareness of all people in this pandemic, a solution to adapt as required. The proponents were able to manifest a solution to such a problem and this was too bespoke to the transport services. Such transport services were vehicle rentals that offered services to various needs of different people whether it be for creational, business, utility or emergency. The study Vehicle Management and Monitoring System solved the problem of vehicle rental services in this time of pandemic that helped not only the vehicle rental services owners but those who needed such service and as a few steps contributed to the recovery of the country’s economy. The said research used the newest web technologies like cloud servers and mapping technologies like Google map for vehicular monitoring and with the internet's communication capability. The proponents conducted an Online -Survey Questionnaire for one -hundred respondents using a free online tool from Google called Google Forms. The results showed that the study not only offers safety during this pandemic, but also the transactions within vehicle rentals to be faster, organized, efficient and gives the feeling of progress for all their users.

### Web-Based Qualifying Examination for Accountancy Students of Don Honorio Ventura State University – Main Campus

UUID: `11fdc7b9-4308-4e65-ac11-b57be86f8550` · [open thesis](http://localhost:5173/repository/11fdc7b9-4308-4e65-ac11-b57be86f8550)

Stored keywords: paper-based examination, web-based qualifying examination, digitized, database, data records, user-friendly, graphic user interface

Designed for the College of Business Studies at DHVSU Main Campus, this web-based examination platform digitizes the annual qualifying assessment for Bachelor of Science in Accountancy students. Developed using ASP.NET, SQL Server, and an Agile framework, the system replaces paper-based examinations by providing automated real-time scoring, secure question-bank administration, and digital reviewer modules. Testing by 324 students and faculty members confirmed the platform's reliability, accuracy, and ease of operation.

### SISTEMA de OBRA: TRAINING MONITORING SYSTEM

UUID: `53601b50-dde7-42bc-b1c2-a417a3f57cb3` · [open thesis](http://localhost:5173/repository/53601b50-dde7-42bc-b1c2-a417a3f57cb3)

Stored keywords: Sistema de Obra, Training Monitoring System, Agile Software, ISO, Web-Based Approach

Developed for the Municipal Social Welfare and Development Office (MSWDO) of Bacolor, Pampanga, Sistema de Obra is a web-based training monitoring and management platform designed to replace outdated paper and spreadsheet systems. Built through Agile software development, the platform streamlines trainee registration, scheduling, progress monitoring, and heatmap-based reporting while enforcing role-based access control. Evaluation based on ISO/IEC 25010 standards yielded an overall score of 3.49 ("Highly Acceptable"), confirming its operational efficiency and effectiveness.

### Web-Based Equipment Maintenance Monitoring System for DHVSU Facilities

UUID: `e5aac843-a9ed-4be6-a45e-64f29da466d8` · [open thesis](http://localhost:5173/repository/e5aac843-a9ed-4be6-a45e-64f29da466d8)

Stored keywords: QR code generator, QR scanner, Equipment requests

A web-based equipment maintenance monitoring and inventory system developed for the Procurement and Supply Management Office (PSMO) and facility custodians at Don Honorio Ventura State University. Utilizing Agile development and the Kanban framework with Laravel and MySQL, the system replaces manual paper forms by digitizing maintenance requests, service status tracking, and inventory auditing using integrated QR code generation and scanning. Evaluation under ISO/IEC 25010 standards resulted in an overall rating of 3.36 ("Very Positive" / "Highly Acceptable").

### ANTABE: AN INTELLIGENT GUIDE STICK FOR VISUALLY IMPAIRED

UUID: `b05abf84-2643-4d03-888b-80fdb187152d` · [open thesis](http://localhost:5173/repository/b05abf84-2643-4d03-888b-80fdb187152d)

Stored keywords: Visual Impairment, Smart Cane, Assistive Technology, Iot

Antabe is an intelligent assistive guide stick designed to enhance spatial awareness, obstacle avoidance, and independent mobility for visually impaired individuals in Guagua, Pampanga. Powered by an Arduino microcontroller, the device integrates ultrasonic sensors for multi-directional obstacle detection, a water hazard sensor, haptic vibration cues, audible buzzer alerts, and a GPS module that sends real-time emergency coordinates via SMS. The prototype demonstrated consistent navigation assistance across alpha (2.92) and beta (2.65) testing.

### AQUAFLOW: AN ARDUINO-POWERED SMART IRRIGATION SYSTEM FOR GUMAIN DAM

UUID: `22f74b8e-7c13-4714-bab3-67e10140965d` · [open thesis](http://localhost:5173/repository/22f74b8e-7c13-4714-bab3-67e10140965d)

Stored keywords: Smart Irrigation System, Arduino Technology, Blynk Application, IoT (Internet of Things), Water Flow Control, Water Level Monitoring

AquaFlow is an IoT-based automated irrigation system developed for agricultural fields connected to Gumain Dam in Floridablanca, Pampanga to reduce water wastage and prevent crop damage from overwatering or drought stress. Built through Rapid Application Development (RAD), the system integrates a NodeMCU ESP8266 microcontroller, ultrasonic water level sensors, a servo motor-controlled irrigation gate, and the Blynk mobile app for remote monitoring and flow management. Evaluation under ISO/IEC 25010 standards resulted in an overall mean score of 3.68 in alpha testing and 3.42 in beta testing.

### COMPAWNION: A PROFILE MANAGEMENT SYSTEM with GEO-LOCATION SYSTEM for NOAH'S ARK DOG AND CAT SHELTER, MABALACAT, PAMPANGA

UUID: `f92512f4-5976-4844-bc95-fcbb77f47f7b` · [open thesis](http://localhost:5173/repository/f92512f4-5976-4844-bc95-fcbb77f47f7b)

Stored keywords: Geo-location, Profile Management, Stray pets, Dogs, Cats, Mabalacat City

Compawnion is a web-based animal profile and rescue management platform created for Noah's Ark Dog and Cat Shelter in Mabalacat City, Pampanga. Developed through an iterative software lifecycle, the system digitalizes sheltered pet records, coordinates adoption applications and donations, tracks vaccination schedules, and integrates GPS geolocation reporting to allow citizens to submit photo reports of stray animals for rapid rescue. Evaluated under ISO 9126 standards, the platform achieved an overall rating of "Excellent" from both residents (4.26) and IT experts (4.00).

### CYBERESCAPE: A MOBILE EDUCATIONAL ESCAPE ROOM APPLICATION FOR NETWORKING FUNDAMENTALS

UUID: `8a1b73df-d71c-4458-82c9-b9721f655b94` · [open thesis](http://localhost:5173/repository/8a1b73df-d71c-4458-82c9-b9721f655b94)

Stored keywords: CyberEscape mobile game application, Educational mobile game, Digital Educational Escape Room, Gamified Learning

CyberEscape is an educational 2D mobile escape room game developed to improve comprehension of networking fundamentals among TVL-ICT Senior High School students at Tomas Dizon Foundation Institute. Built using Unity, C#, Aseprite, and the Octalysis gamification framework under an Agile Kanban workflow, the game translates technical curriculum concepts into interactive room-based puzzles and troubleshooting quests. Pre- and post-testing demonstrated a 17% knowledge gain (56% to 73%), while ISO/IEC 25010 evaluations confirmed high usability and educational engagement.

### DORMIFY: DORM FINDER AND MANAGEMENT SYSTEM WITH GEOFENCING TECHNOLOGY FOR DHVSU MAIN CAMPUS

UUID: `827a721c-0ecc-4896-b9b4-f5571f32736c` · [open thesis](http://localhost:5173/repository/827a721c-0ecc-4896-b9b4-f5571f32736c)

Stored keywords: Dorm Finder, Management System, Geofencing Technology

Dormify is an Android-based dormitory finder and rental management system created for students, faculty, and property owners within a 1-kilometer radius of DHVSU Main Campus in Bacolor, Pampanga. Developed using an iterative model, the application incorporates Google Maps geofencing to display available boarding houses and shortest routes, in-app tenant-landlord communication, real-time vacancy updates, and cashless GCash payment processing. System evaluation under ISO/IEC 25010 achieved an overall score of 3.92 ("Agree") in alpha testing and 4.31 ("Strongly Agree") in beta testing.

### HTEFinder: A Web Application Utilizing Geofencing Technology

UUID: `ca211b67-2032-48e0-90d8-d30c250a7804` · [open thesis](http://localhost:5173/repository/ca211b67-2032-48e0-90d8-d30c250a7804)

Stored keywords: On-the-Job Training, Host Training Establishment, Geofencing Technology, Expert System, Laravel Framework, MySQL Database

HTEFinder is a web-based platform developed to streamline the search and placement process of Host Training Establishments (HTE) for on-the-job training (OJT) students in the College of Computing Studies at DHVSU. Developed with the Laravel framework and MySQL using an iterative approach, the system integrates geofencing boundaries to locate nearby training providers and uses an Expert System algorithm to match student skills with company vacancies. System evaluation under ISO/IEC 25010 achieved overall "Excellent" ratings of 4.92 in alpha testing and 4.88 in beta testing.

### MEMOLOOP: A CUSTOMIZABLE DIGITAL LEARNING FLASHCARDS FOR MEMORIZATION ASSESSMENT

UUID: `2724801d-2dfe-43a7-a941-5d633374baa0` · [open thesis](http://localhost:5173/repository/2724801d-2dfe-43a7-a941-5d633374baa0)

Stored keywords: Digital Flashcards, MemoLoop mobile application, Learning and Memorizing Information

MemoLoop is an Android mobile digital flashcard application engineered to enhance active recall and long-term memory retention for Bachelor of Science in Biology students at DHVSU. Developed using Flutter, Dart, Laravel, and MySQL, the application implements the SuperMemo SM-2 spaced repetition algorithm, customizable decks with image attachments, multimodal answering mechanisms (buttons and speech-to-text), and teacher assessment sections. Heuristic evaluation and testing across 136 biology students demonstrated a usability mean increase from 1.58 to 3.45 and test score improvements ranging from 20.1% to 42.46%.

### MSWD Online Financial Assistance Program Management System with SMS Notification and Status Tracking

UUID: `334eaf14-be5d-45a7-a8d2-5194f924bcf8` · [open thesis](http://localhost:5173/repository/334eaf14-be5d-45a7-a8d2-5194f924bcf8)

Stored keywords: MSWD, Online Financial Assistance, AICS, SMS, OTP, Status Tracking

A web-based application designed for the Municipal Social Welfare and Development Office (MSWDO) in Santo Tomas, Pampanga to digitize the Assistance to Individuals in Crisis Situations (AICS) program. Developed using an iterative methodology connecting the MSWDO, Budget, Accounting, and Treasury offices, the system provides online document submission, multi-office voucher approval workflows, real-time status tracking, and automated SMS alerts for fund releases. System evaluation under ISO/IEC 25010 standards yielded a composite rating of 3.35 ("Strongly Agree").

**Source check:** Source caveat: the manuscript prints an HTEFinder/OJT abstract under its ABSTRACT heading; review that source mismatch before relying on the abstract for grouping.

### A FUZZY LOGIC-BASED MOBILE APPLICATION FOR REAL-TIME MONITORING OF MODULAR INDOOR FARMING

UUID: `8212ab33-5c0e-4b1f-8383-583f1db45722` · [open thesis](http://localhost:5173/repository/8212ab33-5c0e-4b1f-8383-583f1db45722)

Stored keywords: Aeroponics, fuzzy logic algorithm, indoor

An automated indoor aeroponics system and mobile application developed to monitor and manage crucial plant environmental parameters, including temperature, humidity, pH, and water levels. Developed using a Waterfall model for the mobile app and a prototype model for the tower hardware, the system executes an embedded fuzzy logic algorithm on an Arduino microcontroller to determine notification urgency and actuate nutrient misting pumps. Evaluation by local farmers and IT experts under ISO/IEC 25010 standards yielded a grand mean of 3.49 ("Highly Acceptable"), confirming its operational reliability and suitability for sustainable indoor agriculture.

### PALE-NGKIHAN: ONLINE MARKET SYSTEM FOR ARAYAT RICE TRADERS

UUID: `9ade9f3c-ffde-4481-be98-b2605cc3abf1` · [open thesis](http://localhost:5173/repository/9ade9f3c-ffde-4481-be98-b2605cc3abf1)

Stored keywords: online market system, web-based, agricultural, rice trading, middlemen

A web-based e-commerce platform designed to establish a direct trading channel between rice farmers and buyers in Arayat, Pampanga. Developed using Agile methodology, the system eliminates price disparities caused by intermediaries by providing transparent pricing, product cataloging, order tracking, and in-app negotiation features. System testing based on ISO/IEC 25010 software quality standards yielded an overall grand mean of 3.70 ("Strongly Agree"), confirming its usability, transaction security, and commercial viability for the local rice trading sector.

### TASKGROVE: A TREE-BASED PROJECT MANAGEMENT APPLICATION

UUID: `fd8a1ca0-665f-442b-b919-7afe31cdbbc5` · [open thesis](http://localhost:5173/repository/fd8a1ca0-665f-442b-b919-7afe31cdbbc5)

Stored keywords: project management, tree-based, task management, monitoring

TaskGrove is an online platform that is essential in today's project management landscape. Its emergence has brought about a significant revolution in the way tasks are organized within project frameworks, leading to a remarkable increase in productivity levels. This innovative platform not only simplifies the complex process of achieving goals but also ensures the success of projects by providing a seamless and efficient workflow that minimizes errors, setting it apart from outdated manual methods or inadequately designed tools. In this study, the researchers employed a descriptive research design and used quantitative methodology to gauge the preferences of 40 respondents (5 Alpha Testers, 35 Beta Testers) working within the campus and planning office of Don Honorio Ventura State University. The aim was to assess how well the respondents received the web application, considering its functional suitability, performance efficiency, compatibility, usability reliability, security, maintainability, and portability, across various devices. The results gained a total of 3.87 in the Alpha Testing and 4.37 in the Beta Testing. Keywords project management; tree-based; task management; monitoring...

### VAXTRACK: A WEB APPLICATION FOR RABIES VACCINATION TRACKING AND MANAGEMENT

UUID: `2db3a8d8-cf98-4f9e-bcb6-6f4390e069dd` · [open thesis](http://localhost:5173/repository/2db3a8d8-cf98-4f9e-bcb6-6f4390e069dd)

Stored keywords: Web Application, Animal bites, Public Health Concern, Vaccination Tracking and Management, VaxTrack, User-friendly, Accessible, Manage Animal Welfare Information, Rabies Prevention

A web-based rabies surveillance and pet immunization tracking application developed for local government health staff and barangay officials in the City of San Fernando, Pampanga. Developed using the Waterfall SDLC model, the platform digitizes rabies case reporting, multi-pet registration, vaccination record maintenance, and geographic tracking to support early intervention and disease containment. Evaluation by 108 healthcare professionals, barangay personnel, and IT experts under ISO/IEC 25010 standards resulted in an overall grand mean of 3.34 ("Strongly Agree"), validating its efficiency and data reliability.

### ANIDELIVERY: A FARMERS PLATFORM FOR SUSTAINABLE AGRICULTURE THROUGH MACHINE LEARNING-POWERED DIGITAL MARKETPLACE IN PAMPANGA

UUID: `143fb188-2e1a-41f9-8400-ca42466fd8a3` · [open thesis](http://localhost:5173/repository/143fb188-2e1a-41f9-8400-ca42466fd8a3)

Stored keywords: AniDelivery, Digital Marketplace, Supply Chain Management, Over Supply, Under Supply, Consumer

A mobile and web-based digital marketplace created to support sustainable agriculture in Pampanga by facilitating direct transactions between farmers and consumers. Developed using an Agile Scrum methodology, the platform incorporates machine learning algorithms for sales forecasting to mitigate oversupply and undersupply, while providing price monitoring aligned with Department of Agriculture standards, order traceability, and digital payment gateways. System evaluation under ISO 9126 standards with 375 farmers and IT experts yielded an overall mean score of 3.62 ("Strongly Agree"), confirming its usability, efficiency, and commercial viability.

### CODEQUEST: WHEN JAVA PROGRAMMING MEETS PLAYFUL LEARNING

UUID: `3970223e-18b9-45df-88a2-99a83abdee02` · [open thesis](http://localhost:5173/repository/3970223e-18b9-45df-88a2-99a83abdee02)

Stored keywords: Gamification, Blended, Engagement, Effectiveness

CodeQuest is an interactive, web-based 3D gamified educational platform developed to enhance Java programming instruction through a blended learning approach. Developed using React.js, Three.js, Node.js, and PostgreSQL under the Agile Scrum framework, the system integrates quest-based programming challenges delivered by NPCs, immersive 3D world navigation, and an embedded Ace Code Editor providing real-time syntax execution and debugging feedback. Quality of Experience evaluation under ISO/IEC 21838 standards yielded grand means of 3.57 ("Agree") from alpha testers and 4.28 ("Strongly Agree") from 100 computing students, confirming its effectiveness in increasing learner engagement and concept comprehension.

### DHVCHAT: A WEB-BASED INTELLIGENT CHAT ASSISTANT FOR THE ADMISSIONS OFFICE USING NATURAL LANGUAGE PROCESSING

UUID: `18737b6e-983a-4ae6-915a-8f155aefb160` · [open thesis](http://localhost:5173/repository/18737b6e-983a-4ae6-915a-8f155aefb160)

Stored keywords: Natural Language Processing, chatbots, university admission, AI-enhanced communication systems

DHVChat is an AI-powered conversational web assistant created for the Admissions Office of Don Honorio Ventura State University to automate student inquiry handling. Built using ReactJS, Python, and OpenAI's GPT-3.5 Turbo text embeddings within an iterative waterfall methodology, the system provides automated answers to common admission queries regarding requirements, schedules, and program details while rerouting unresolved concerns to admissions personnel. System evaluation based on ISO/IEC 25010 standards yielded a high overall satisfaction rating of 3.51 ("Strongly Agree"), demonstrating a marked improvement over traditional manual communication channels

### Revolución: A Side-Scroller Rpg For Learning The Philippine Spanish Revolution Through An Exciting And Educational Adventure

UUID: `eabd1c88-7956-4f2f-9c3f-35e943079ab1` · [open thesis](http://localhost:5173/repository/eabd1c88-7956-4f2f-9c3f-35e943079ab1)

Stored keywords: Educational Game, Game -Based Learning, Side -Scroller RPG, Godot Engine, Philippine Spanish Revolution, Interactive Learning, MEEGA+ Eval- uation Model, Pixel Art, Story-Based Learning, Grade 6 History Education

This study developed Revolución: A side-scroller RPG for Learning the Philippine-Spanish Revolution through an Exciting and Educational Adventure, to address learning about the Philippine -Spanish Revolution among Grade 6 students of Pulung Santol Elementary School. The researcher employed the Agile Methodology, incorporating user feedback through iterative design cycles. The platform provides an educational game that engages learners in historical playing and teachers can use it as a supplementary tool for classroom lessons through interactive gameplay. The learners are directed by story-based missions to key events of the Philippine Spanish Revolution and supported by in-game journals, quizzes, and character interactions. Testing involved both alpha and beta evaluations. Three alpha testers, consisting of three IT experts, assessed the system during its initial phase. In the beta phase, 116 respondents evaluated the system by indicating high satisfaction regarding Usability, Player Experience, and Learning Experience. Results demonstrate the system's ability to optimize learning of the Grade 6 Students by having an engaging and immersive gameplay through action, storytelling, and exploration, players experience key events, places, and figures from the eight pioneering provinces and meet significant people. The game offers an interactive, user-friendly UI and an enjoyable gaming experience while learning history.

### Web-Based Grading System With Data Analytics For The Modernized Processing Of President’s And Dean’s Lists Candidates

UUID: `a634c87e-abe4-486c-b9d7-29f6fa9585a8` · [open thesis](http://localhost:5173/repository/a634c87e-abe4-486c-b9d7-29f6fa9585a8)

Stored keywords: web-based system, data analytics, manual processing, grade verification, Optical Character Recognition (OCR)

This study addresses the inefficiencies of the manual processing of President’s List (PL) and Dean’s List (DL) applications at Pampanga State University, which is time-consuming and prone to delays. A web-based system was developed to streamline registration, grade computation, verification, ranking, and reporting processes. The system features a secure, role-based login, an automated grading module that notifies eligible students for academic honors, a verification and approval workflow to authenticate and approve submissions, and integrated data visualization of students’ grades, which provides performance insights for decision-making. To achieve this, a mixed methods approach was employed, therefore, quantitative data is collected from students and IT experts via a 5-point Likert scale questionnaire, meanwhile open-ended questions are asked to the College of Computing Studies Student Council governor to gather information regarding manual processing. Evaluation results based on ISO 25010 Software Quality Standards revealed that the system was rated “Highly Acceptable” across all attributes, including Functional Stability, Performance Efficiency, Compatibility, Usability, Reliability, Security, Maintainability, Portability, and Quality in Use, which indicates that the system is reliable, responsive, and functional. Therefore, the proposed system modernizes the PL/DL process by offering a centralized, secure, and efficient platform that benefits both students and stakeholders, which enhances accuracy, transparency, and overall operational efficiency.

### SINDALAN CONNECT: A NEXT GENERATION LOCAL COMMUNITY MANAGEMENT SYSTEM POWERED BY AI CHATBOT AND EMERGENCY RESPONSE

UUID: `7203d29b-4dba-4ede-aa25-335ef85707a5` · [open thesis](http://localhost:5173/repository/7203d29b-4dba-4ede-aa25-335ef85707a5)

Stored keywords: Barangay Information System, E-Governance, Digital Public Services, Emergency Response System, AI Chatbot, Incident Reporting, Online Permit Application, Rural Health Unit Announcements, Community Engagement

As people today expect faster, more convenient, and more responsive public services, the system brings together modern digital tools to improve how the barangay works and how it engages with the community. Sindalan Connect automates essential services like online permit applications, certificate requests, blotter reporting, and filing of complaints, all supported by a 24 -hour AI chatbot that assists users anytime they need help. One of its central features is the Emergency Response Module, which allows residents to report incidents such as fires, crimes, or medical emergencies in real time, helping barangay officials respond faster through automated SMS alerts and organized incident tracking. The system also includes a Rural Health Unit announcement function that delivers timely updates on vaccination drives, medical missions, and health advisories, ensuring that important health information reaches residents quickly. To ensure quality, the platform was evaluated using the ISO 25010 software standards, assessing its functionality, usability, reliability, security, and overall performance. Although challenges such as limited internet access, varying levels of digital literacy, and differences in device compatibility may affect user experience, Sindalan Connect still aims to make barangay services more efficient, more transparent, and more accessible.

### ShopEase: AN IOT-BASED SHOPPING CART WITH BARCODE SCANNER AND REAL-TIME MULTI-CART MONITORING SYSTEM

UUID: `3ee906b3-2e8d-4da9-b155-5a70c69ba4fa` · [open thesis](http://localhost:5173/repository/3ee906b3-2e8d-4da9-b155-5a70c69ba4fa)

Stored keywords: IoT (Internet of Things), Real-Time Monitoring, Multiple Carts, Cashier Application

Traditional supermarket checkout methods create significant friction for customers, often resulting in long queues and reduced operational efficiency. To resolve these challenges, this study developed ShopEase: An IoT-Based Shopping Cart with Barcode Scann er and Real-Time Multi-Cart Monitoring System. The system integrates a Raspberry Pi 5, barcode scanner, and touchscreen monitor directly into the shopping cart, enabling customers to scan their own items and view a running total in real-time. All transacti onal data is managed and instantly synchronized using the Firebase Real-Time Database. The core innovation lies in the Real-Time Multi-Cart Monitoring feature of the Cashier Application, which provides cashier with immediate administrative oversight, allow ing them to track the transaction details of multiple active carts simultaneously. Although the ShopEase System is designed as a prototype and currently limited to cash payment only and requires stable internet connectivity, it successfully demonstrates how IoT technology can fundamentally enhance retail efficiency and the customer experience. Overall, the study contributes to streamlining the checkout process and improving the customer shopping experience.

### Rehirely: A Mobile-Based Application For Job-matching For Senior Citizen Employment

UUID: `c7d80880-8132-4163-b6fb-4ae63573e4ca` · [open thesis](http://localhost:5173/repository/c7d80880-8132-4163-b6fb-4ae63573e4ca)

Stored keywords: mobile application, job matching, digital inclusion, active aging, age - inclusive employment, employment technology, user-centered design, RAD methodology, ISO/IEC 25010

REHIRELY is a mobile -based job-matching application developed to help senior citizens aged 60 and above in Pampanga access local employment opportunities through a secure and user -friendly digital platform. The system was designed to address challenges such as digital exclusion and age-related bias in hiring by providing simplified navigation, personalized job recommendations, and administrative support in partnership with the Office for Senior Citizens Affairs (OSCA). The study utilized a quantitative descriptive research design and followed the Rapid Application Development (RAD) methodology for system development. The application was evaluated through alpha and beta testing involving 103 participants, including senior citizens, local employers, and IT experts. System quality was assessed using the ISO/IEC 25010 Software Product Quality Model. Results showed high user satisfaction across key quality attributes, including Functional Suitability, Reliability and Performance, and Usability, with an overall grand mean of 3.67, interpreted as Highly Acceptable. The findings confirm that REHIRELY is a valid, reliable, and effective digital solution that supports active aging and promotes digital inclusion by connecting senior citizens with meaningful employment opportunities.

### ChemLab AR: AUGMENTED REALITY-BASED CHEMISTRY EXPERIMENTS

UUID: `e2d47493-770e-4d2a-bf73-c6c191258fe0` · [open thesis](http://localhost:5173/repository/e2d47493-770e-4d2a-bf73-c6c191258fe0)

Stored keywords: Augmented Reality (AR), Ball-and-Stick Models, Chemical Reaction, Chemistry Education, Molecular Geometry, Mobile Application, Virtual Laboratory, 3D Visualization

The lack of sufficient laboratory equipment in Philippine public schools significantly hinders the effective learning of general chemistry concepts such as molecular structures and chemical reactions. To take aim at this educational gap, the "ChemLab AR" Android mobile application was developed, integrating Augmented Reality (AR) and 3D technology to offer a safe, interactive, and accessible virtual laboratory experien ce that simulates real -world chemistry procedures without physical hazards. The system features four interactive modes, “Elements”, “Burn”, “Mixing”, and “Modules.” The study utilized a descriptive quantitative research design and the Agile Development Met hodology, guided by the ISO 9241-210 human computer interaction. The system was evaluated by three IT experts and 205 Senior High School students from Floridablanca National Agricultural School. The system was rigorously evaluated by a panel of three IT experts and two hundred five (205) Senior High School students from Floridablanca National Agricultural School. The evaluation results indicated a highly positive reception, with respondents strongly agreeing that the application effectively demonstrates the outcome of combining elements and provides a suitable range of fundamental chemistry topics. In conclusion, the application serves as a cost effective, safe, and innovative alternative for resource -limited schools. Transforming how chemistry is taught and learned.

### CyberDefender: A Game-Based Learning Platform for Enhancing Students' Cyber Threat Awareness

UUID: `10416ed7-4445-456d-9c4c-c9504765e40f` · [open thesis](http://localhost:5173/repository/10416ed7-4445-456d-9c4c-c9504765e40f)

Stored keywords: Cybersecurity, Roblox, Agile, ISO 25010

The educational game CyberDefender was developed with the aim of helping to solve the growing cybersecurity awareness problems among students, through the use of interactive game-based learning. This means finding innovative ways to increase their knowledge about the risk of cyber threats, which i s growing daily and to which students are increasingly exposed. Based on this scenario, the researchers created the game CyberDefender in Roblox Studio to teach basic concepts of cybersecurity through missions and scenario -simulated cyber incidents. The sy stem was developed using the Agile methodology, and its evaluation involved both alpha and beta testers, who assessed the platform using the ISO/IEC 25010 software quality model. The findings of this study demonstrate that CyberDefender successfully met all of its research objectives, as shown by its strong performance across the ISO 25010 software quality standards, earning high ratings in functional suitability (3.59), performance efficiency (3.52), usability (3.46), reliability (3.48), and other criteria, resulting in an overall grand mean of 3.54. In light of these results, the researchers recommend enhancing CyberDefender by integrating Artificial Intelligence to generate dynamic mission variations, expanding the range of cybersecurity concepts beyond th e current mission set, and implementing an AI -driven adaptive difficulty system that adjusts challenges based on player performance. These improvements would increase deepen learning and ensure that the game remains engaging, accessible, and educational for students with varying levels of cybersecurity knowledge.

### My Honorian Buddy: A Web-Based Peer-Tutoring System For The Students Of Pampanga State University

UUID: `2784252f-6995-4ce5-be72-87dd0d1276f1` · [open thesis](http://localhost:5173/repository/2784252f-6995-4ce5-be72-87dd0d1276f1)

Stored keywords: peer-tutoring, web-based, content-based algorithm

The increasing integration of technology in education has amplified the need for personalized academic support, particularly in online learning environments. My Honorian Buddy is a web-based peer-tutoring system that connects students one-onone with suitable peer tutors using a content -based matchmaking algorithm considering academic requirements, subject preferences, and availability. The system aims to provide focused, flexi ble, and personalized academic support, promoting deeper learning, motivation, a nd engagement among students at Pampanga State University. This qualitative study evaluated the system’s effectiveness, usability, and adherence to quality standards using the ISO/IEC 25010 model. Alpha testing involved IT professionals, while beta testing gathered feedback from 382 students across different coll ege departments through simple random sampling. Structured Likert-scale questionnaires measured functional suitability, performance efficiency, compatibility, reliability, security, maintainability, flexibility, interaction capability, and safety. Results indicated that the system met expected quality standards, with mean scores ranging from 3.17 (Functional Suitability) to 3.56 (Safety). The overall grand mean of 3.36 reflects high acceptability, demonstrating that My Honorian Buddy is an effective, reliable, and user -friendly system for personalized peer -tutoring.

### Headlink: An Iot-Powered Head Pose Tracking System For Assistive Input And Human-Computer Interaction

UUID: `1bb71d5b-494c-452b-89e3-28ecafd4a81a` · [open thesis](http://localhost:5173/repository/1bb71d5b-494c-452b-89e3-28ecafd4a81a)

Stored keywords: Head Pose Tracking, Assistive Technologies, Human-Computer Interaction, Gesture-Based Inputs, Raspberry Pi, IoT System

HeadLink is an IoT-Powered Head Pose tracking system designed to make computers more accessible by providing a hands-free alternative for human-computer interaction. It uses computer vision and facial landmarking to track head position and translate it into mouse movements and functions. HeadLink addresses challenges faced by physically impaired individuals, specifically those with limited hand mobility to use traditional input devices such as a mouse. HeadLink aims to offer an intuitive head-controlled input solution via a Raspberry Pi camera-based architecture and custom developed python software that lets users communicate with the external device. The system went through a series of evaluation phases adhering to the ISO/IEC 30141:2024, a framework for IoT-Based Systems. During the alpha testing phase, IT professionals evaluated the system’s performance based on 5 categories. The beta testing involved BSIT and BSCS students from Pampanga State University and individuals with limited hand mobility to assess the performance of the device in real-world situations. Both tests used a 4-point Likert scale to gather necessary feedback about HeadLink's performance. Results showed an overall weighted average of 3.54, interpreted as “Strongly Agree”, which proves that HeadLink was indeed functional and capable of facilitating head-pose-based interaction.

### iSecure: An Integrated Web-Based System for Base Access and Security Operations

UUID: `a23823a2-bda9-4a96-9ed4-085d0a24b6e7` · [open thesis](http://localhost:5173/repository/a23823a2-bda9-4a96-9ed4-085d0a24b6e7)

Stored keywords: iSecure, Access Control, RFID, Facial Recognition, OCR, Security Operations, ISO/IEC 25010, Agile Scrum

In areas that needs high security people often use outdated paper-based systems to track and archive record. This can, in turn, run into problems due to human error and inefficiencies. The goal of this project was to develop a web-based system named iSecure that automates security procedures in order to reduce wait times and minimize human error. The iSecure system used technology like Radio Frequency Identification (RFID) to keep track of people and give them access to parts of the base, Optical Character Recognition (OCR) to automatically extract information from vehicles and identification cards, and facial recognition (Machine learning) to verify a person’s identity. The researchers used the Developmental and Descriptive research design and worked with the Agile Scrum Framework for the software development life cycle. The system was tested by 47 people, including 2 alpha testers (IT experts) and 45 beta testers (Security Personnel and Users), based on the ISO/IEC 25010 Software Quality Model. The testers who evaluated the system provided an overall mean score and stated that it is well-made and well-suited for gate clearance. The system efficiently processed individuals at the gate and maintains data integrity, ensuring that records of those who pass through are accurate and secure.

### Barangaymed+: A Hybrid Application With Inventory And Healthcare Service System For Barangay Health Centers In Municipality Of Floridablanca, Pampanga

UUID: `942ded1d-9463-40d0-bdff-796f6add7f1d` · [open thesis](http://localhost:5173/repository/942ded1d-9463-40d0-bdff-796f6add7f1d)

Stored keywords: BarangayMed+, digital health, teleconsultation, inventory management, healthcare system, ISO/IEC 25010, barangay health centers

Barangay health centers serve as the primary access point for basic healthcare in the Philippines, yet many continue to depend on manual processes that result in long queues, inefficient record handling, delayed access to medicines, and limited communication with residents. This study developed BarangayMed+, a hybrid application designed to enhance healthcare service delivery and inventory management across the 33 barangays of Floridablanca, Pampanga. The system features real -time medicine availability chec king, digital medicine requests, teleconsultation scheduling, medicine expiry monitoring, and role-based access for Residents, Barangay health workers (BHW), and Rural Health Unit (RHU) staff. Using developmental and descriptive research methods and guided by the Scrum Framework, the system underwent alpha and beta testing aligned with the ISO/IEC 25010 Software Quality Model. A total of 100 participants evaluated the system’s functionality, usability, security, and performance. Results showed ratings fro m Very Good to Excellent, indicating that the system successfully met its proposed objectives. Overall, BarangayMed+ demonstrates strong potential to improve healthcare delivery by efficient processes, reducing administrative workload, and providing residents with timely access to health services. The system may also serve as a scalable model for other municipalities seeking to modernize barangaylevel healthcare.

### Attachmates: A Dating App For Ai-Powered Compatibility-Based Matching Through Attachments Styles And Love Languages

UUID: `c1b8c2f6-69c3-47f6-80cb-ecaa3fb79c1c` · [open thesis](http://localhost:5173/repository/c1b8c2f6-69c3-47f6-80cb-ecaa3fb79c1c)

Stored keywords: attachment styles, love languages, dating fatigue, hybrid recommendation system, psychology-based matching, Flutter, Firebase, AI matching

Many dating applications today prioritize physical appearance and fast interactions, often leading to emotional mismatches, inconsistent connections, and dating fatigue among users. This study focused on development of AttachMates, a dating application designed to improve compatibility by integrating attachment styles and love languages into its matchmaking process. Guided by Attachment Theory and the Five Love Languages Framework, the project aimed to create a hybrid recommendation system, reduce dating fatigue through supportive features, and ensure secure data handling using Firebase while following ISO and IEC quality standards. A descriptive developmental research design was used, following the Waterfall Model from requirement analysis to system design, development, and testing. The application was built using Flutter for the user interface, Firebase and Supabase for data storage, and Python for the AI-driven matching algorithm. Results from user testing showed that participants found the assessments simple, the interface easy to use, and the suggested matches more meaningful compared to typical dating apps. Users also reported gaining more awareness of their attachment styles and love language preferences. Overall, the findings highlight the value of psy chology-based matching in improving online dating experiences and supporting healthier romantic connections. The study concludes that AttachMates shows strong potential as a compatibility -centered dating platform. Recommendations include scaling the system for broader use, enhancing relationship guidance features, improving the AI model with more extensive datasets, and developing an iOS version to increase accessibility.

### DormHonorio: DORMITORY BOOKING AND ALGORITHM-DRIVEN ROOMMATE MATCHING MOBILE APPLICATION FOR HONORIANS

UUID: `7aa5c31d-8be0-4e1b-b4aa-1b6a87bb016c` · [open thesis](http://localhost:5173/repository/7aa5c31d-8be0-4e1b-b4aa-1b6a87bb016c)

Stored keywords: weighted scoring algorithm, roommate matching, dormitory, tenant

The goal of this study was to develop DormHonorio, a mobile application that helps Pampanga State University students find dormitories and compatible roommates in a more organized and reliable way. Since there is still no official online platform for this purpose, students often experience a stressful search process and end up with roommates they don’t match well with, affecting their comfort and studies. DormHonorio was created to lessen these issues and make the search easier. For the development process, the researchers used the Agile method with a Kanban board so tasks could be handled step-by-step and adjusted when necessary. A key feature of the system is its weighted scoring algorithm for roommate matching, which checks specific factors to help students find someone they are more likely to get along with. To evaluate system quality, IT professionals assessed the app using ISO 25010 standards. Results showed that DormHonorio passed all 9 required criteria and performed well. The system was also tested by 100 beta testers, who gave an overall rating of 4.42, and 3 alpha testers, who gave a rating of 4.69. In the end, this study successfully developed a working and reliable mobile application that organizes dormitory information and provides an effective, algorithm-based approach to matching tenants with compatible roommates. DormHonorio offers Pampanga State University students a more convenient and supportive way to find dorms and live with people they match well with.

### AnImo: An AI-Driven Agricultural Hybrid Platform with Intelligent Crop Recommendations and IoT-Enabled Solar-Powered Water Irrigation Based on Soil Analysis

UUID: `b1f3b63d-16ce-4458-8224-163564b61a8a` · [open thesis](http://localhost:5173/repository/b1f3b63d-16ce-4458-8224-163564b61a8a)

Stored keywords: Gemini, Internet of Things, Smart Farming, Solar -Powered Water Pump, Soil Analysis

Local farmers in the Philippines face significant challenges, including fluctuating market prices, soil degradation, and climate variability, which contribute to low productivity and economic losses. Addressing the urgent need for innovative technological solutions, this project developed AnImo: An AI -Driven Agricultural Hybrid Platform with Intelligent Crop Recommendations and IoT -Enabled Solar - Powered Water Irrigation Based on Soil Analysis for agriculturalists in Pampanga. AnImo is a hybrid system utiliz ing the Gemini AI model to generate data -driven soil recommendations and crop suggestions, complemented by a comprehensive planner for farming reminders. The platform also integrates an IoT-enabled soil sensor with a solarpowered irrigation system for con tinuous soil monitoring and automated water management, significantly enhancing resource efficiency. The study employed an iterative software development methodology, incorporating user feedback via pre - and post-surveys to ensure practical relevance. Quan titative analysis and system evaluation found that AnImo meets the standards of ISO 25010 and ISO 38507, while supporting UN Sustainable Development Goals 2, 8, and 13. The testing phase yielded a high combined mean score of 3.43, verbally interpreted as " Strongly Agree", confirming the platform's effectiveness in addressing critical agricultural challenges, including crop suitability, irrigation, and overall farm profitability. Future research should prioritize expanding the system's locale across the Philippines, integrating a smart chatbot for user support, and developing AI recommendations based on comprehensive crop history to further optimize system value.

### ARAL: An Android-based 3D Virtual Learning Material for Preschool Students

UUID: `a5d4a3d3-378c-4f59-b6f0-b3144cbc52e4` · [open thesis](http://localhost:5173/repository/a5d4a3d3-378c-4f59-b6f0-b3144cbc52e4)

Stored keywords: 3D, Android, C-sharp (C#), Platform, Unity3D, Virtual Learning Environment (V.L.E), Structured Query Language (SQL), Windows, XAMPP

The A.R.A.L. an Android-based 3D Virtual Learning Material for Preschool Students is a 3D Virtual and interactive learning material for visual presentation of alphabets, shapes, colors, and numbers. The study was proven an effective teaching aid for teachers and to use the 3D virtual learning material for preschoolers. The A.R.A.L application allowed learners to experience 3D virtual interactive objects that help in giving them a visual presentation rather than a plain text or image. The evaluation of the A.R.A.L. application used an iso-9126 format for the online questionnaire where the respondents found the software a good alternative learning material for preschoolers. The post-survey gathered an overall mean of 4.2 that indicated positive feedback from the respondents. Based on the evaluation of respondents who agreed, the A.R.A.L. application is engaging and motivates preschool students.

### Development of Complaints and Grievances Management System Aligned with R.A. No. 11313

UUID: `2c902b58-ba62-4198-b663-fc72afbec25c` · [open thesis](http://localhost:5173/repository/2c902b58-ba62-4198-b663-fc72afbec25c)

Stored keywords: Case Management, Republic Act No. 11313, Safe Spaces Act, Web-Based System, Grievance Management, Gender-Based Sexual Harassment, ISO/IEC 25010

This study addresses the ongoing problems within Pampanga State University, particularly in the College of Computing Studies, which manages the complaint filing, delayed process, privacy violation, and unsettled cases for taking legal actions. To resolve these issues, the researchers developed a web-based Complaint and Grievances Management System (CGMS), this system complies to the Republic Act No. 11313, also known as Safe Spaces Act. The system offers a user-friendly platform for staff, instructors, and students to file a complaint, monitor the status of their cases, and get notification. Data were gathered via survey questionnaires which include alpha and beta testing, and expert insights, as the researchers utilized a quantitative research design in this study. Stakeholders also participated in evaluating the system based on the compliance to the ISO/IEC 25010 software standard. Functional Suitability (3.58), Performance Efficiency (3.69), Compatibility (3.56), Reliability (3.64), Security (3.70), Portability (3.66), Maintainability (3.67), and Usability (3.57) interpreted as “Highly Acceptable.” The overall grand mean was 3.63, also interpreted as “Highly Acceptable,” reflecting that respondents from the department of CCS agree that the accessibility, privacy, confidentiality, and effectiveness of the system can still be improved. As a result, the implementation of CGMS in this study serves as a dependable and efficient instrument when it comes to supervising a secure, private, and useful grievance file reporting which is aligned to the RA 11313. As the system utilizes a safer learning space, and supports the institutional integration to the safety standards, fairness, and balanced policies by a digital complaint procedure.
