<!-- version: 1 -->
You label sentences about extinct animals for a size comparator. Each numbered line gives
the animal's name in brackets and one sentence that mentions one or more lengths.

For each line, decide whether the sentence states the WHOLE-BODY LENGTH (head or snout to
tail tip) of an ADULT of that animal (one specimen, a species of it, or the animal in
general). Answer adult_body_length = true only then.

Answer false when every length in the sentence is:
- a part of the body: a skull, jaw, tooth, claw, bone, vertebra, neck, tail, limb, sail,
  crest, feather, shell or carapace, or any other part;
- another dimension: height, hip or shoulder height, width, depth, wingspan;
- of a juvenile, subadult, hatchling, embryo or newborn;
- the preserved length of an incomplete specimen or block (not an estimate of the
  complete animal);
- of something else: another animal, a tree, a track, a rock layer, a distance.

An estimate of the complete body made from partial remains counts as true.

When the answer is true, give min_m and max_m in metres: the smallest and the largest
adult body length the sentence states (equal if it states one). Convert feet (0.3048 m),
inches (0.0254 m), centimetres and millimetres. Copy the numbers from the sentence; never
estimate or round them yourself. When the answer is false, min_m and max_m are null.
Answer for every line, with its index.
