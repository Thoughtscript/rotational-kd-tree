# Rotational K-D Tree

So I was mindlessly, listlessly, doomscrolling on Youtube when I encountered [this](https://www.youtube.com/shorts/AN0XXpZXqU0) (or rather it encountered me after surfacing in my recommended activity feed). Got me thinking (as I'm prone to do):

1. Can **Quadtrees** be extended to the three dimensions? A forest of Quadtrees ("forests" of tree-graphs are a useful metaphor in many famous algorithms).
1. Can we exploit something like **Polar Coordinates** (or, better [paths](./000000000138) on the surface of a **Sphere**) to help optimize or fix the projected quadrant that some piece of data would reside in?
1. How efficiently can we reuse data by rotating or transforming data within a "Cubetrees"?

## Initial Thoughts

> So, I learned about **KD-**, and **Ball Trees** but didn't really find anything about using three-dimensional **K-D Tree** within a **Sphere** (whose corners intersect the surface of the **Sphere**). Might just be ignorant here.

There are some probably fairly mundane observations here (but maybe not so obvious to me):
1. The **Rotational Group** for the interior **Cube** (being rotated in every which way about the same origin) forms the same enclosing **Sphere**.
1. That **Rotational Group** in turn appears to be akin a **Linked List** and can be potentially thought of as such.
1. If so, then there are some potential advantages. 
    * We can build a metaphorical **K-D Tree** *forest* out of a *single* three-dimensional **K-D Tree**.
    * We could potentially use **Polar Coordinates** to fix which **Rotation** we intend to use.
    * We can potentially embed into those **Polar Coordinates** a cipher or other data transformation function to have the original **Cube** do multiple-duty - reusing a finite data set in an infinite number of useful ways (think of an **Alphabet** with a fix number of charcters that can be mapped to an infinite number of combinations resulting in words, sentences, phrases).
    * These need not be **Polar Coordinates** alone, they can be a path to allow greater flexibility in retrieving and encoding data.

I had ChatGPT generate a GIF since I couldn't find one to illustrate this point:

![KDTS](cube_rotating_spherical_sweep.gif)

## Some Nascent Research

So, apparently the consensus is:
* "Standard axis-aligned k-d trees are not naturally suited for the curved surface of a sphere because their straight, axis-aligned splitting hyperplanes cannot cleanly handle polar coordinate wraparound or spherical geometry."
"Spatial partitioning trees such as the kd-tree [4–6], quadtrees and higher dimensional variants [7], and vp-trees [8] can efficiently handle exact nearest neighbor searching in lower dimensions. These structures generally perform well on data in a Euclidean metric space, but because of their partitioning mechanism (e.g., axis-aligned splits), they do not readily adapt to the rotational group
SO(3)." - https://robotics.cs.unc.edu/publications/Ichnowski2014_WAFR.pdf
* "...there has to be a unique ordering on the points to determine the resulting k-d tree uniquely." - https://arxiv.org/pdf/1903.04936/1000
* https://faculty.cc.gatech.edu/~vempala/papers/kdtrees.pdf

The upshot:  **KD-Trees** are cutting edge as of 2026 and academics are working to overcome certain limiting properties to enhance their utility. Projecting a **KD-Tree** onto the surface of a Sphere is an active subtopic but there seems to be little in the way of considering **KD-Trees** as a **Rotational (Symmetry?) Group** or affixing the orientation of a Euclidean rotated **KD-Tree** (about its origin) to a specific set of Spherical Coordinates.

> Of course this is all very quick. There's more to be researched and verified!

## Some Definitions and Properties

Before we get to some code:
* A **Cube**'s maximal **Rotational Symmetry Group** is the **Chiral Octahedral Group**. We probably want something with more *degrees of freedom* which is apparently something like a **Linear / Non-Rigid Ambient Group**.
* Can we treat each rotation of the same underlying data and **Cube** as a distinct data set?
* Each rotation can be represented or uniquely captured by a set of **Spherical Coordinates**. 
    * These can represent or be a **Hash**.
    * Serve as a **Linked List** (with the data of each Node being a specific **KD-Tree**).
    * It can serve as meta-data indicating the way to uniquely retreive the underlying data of the **KD-Tree** (which is an excellent and efficient data structure with many of the best (and better than the) characteristics of **Binary Search Trees**, **Cube Trees**, etc.)

## Resources and Links

1. https://www.geeksforgeeks.org/dsa/quad-tree/
1. https://www.geeksforgeeks.org/machine-learning/ball-tree-and-kd-tree-algorithms/
1. https://robotics.cs.unc.edu/publications/Ichnowski2014_WAFR.pdf
1. https://arxiv.org/pdf/1903.04936/1000
1. https://faculty.cc.gatech.edu/~vempala/papers/kdtrees.pdf
