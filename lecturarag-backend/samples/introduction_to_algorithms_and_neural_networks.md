# Introduction to Algorithms & Neural Networks

This lecture connects two ideas that power modern software: the design of efficient algorithms and the training of neural networks. It covers how algorithms are measured, the recurring patterns behind fast solutions, and how those same optimization ideas drive gradient-based learning in deep networks.

## What Is an Algorithm?

An algorithm is a finite, ordered sequence of unambiguous instructions that transforms a set of inputs into a desired output. Correctness, termination, and efficiency are the three properties every algorithm must satisfy before it is useful in production.

Pseudocode describes an algorithm in structured natural language that is independent of any programming language. A good pseudocode description names its inputs, its output, and the loop invariants that explain why each step preserves correctness.

## Measuring Efficiency

Time complexity describes how the number of elementary operations grows as the input size n grows. Big-O notation expresses an upper bound on that growth and deliberately ignores constant factors and lower-order terms.

Binary search runs in O(log n) time because each comparison halves the remaining search space. Space complexity measures the extra memory an algorithm needs beyond its own input, which is why an in-place sort is often preferred on memory-constrained devices.

## Core Algorithmic Patterns

Divide and conquer is a strategy that splits a problem into independent subproblems, solves each recursively, and combines the partial results. Merge sort is a divide-and-conquer algorithm that sorts n items in O(n log n) time and needs O(n) additional space for merging.

Dynamic programming is an optimization technique that stores the answers to overlapping subproblems so each one is solved only once. A problem is a good fit for dynamic programming when it has optimal substructure and overlapping subproblems; the Fibonacci sequence and edit distance are classic examples.

Greedy algorithms build a solution one locally optimal choice at a time and never reconsider earlier decisions. Dijkstra's algorithm is a shortest-path algorithm that requires non-negative edge weights and runs in O((V + E) log V) time with a binary heap.

## From Algorithms to Neural Networks

A neural network is a layered collection of parameterized functions that learns patterns from data by adjusting its weights. Training a network is itself an optimization problem: define a loss function, compute its gradient, and move the parameters downhill.

The perceptron is the simplest neural building block: it computes a weighted sum of its inputs and passes the result through an activation function. A perceptron can only separate data that is linearly separable, which is why multi-layer networks are needed for realistic problems.

## How a Neuron Computes

Each neuron multiplies its inputs by learned weights, adds a bias term, and applies a non-linear activation. The activation function introduces non-linearity; without it, any stack of layers would collapse into a single linear transformation.

The ReLU activation returns the input when it is positive and zero otherwise. ReLU is popular because it is cheap to evaluate and it reduces the vanishing-gradient problem that plagued sigmoid networks.

## Training with Backpropagation

Backpropagation is the algorithm that applies the chain rule of calculus to compute the gradient of the loss with respect to every weight in the network. The forward pass caches intermediate activations, and the backward pass reuses them to propagate error signals layer by layer.

Gradient descent updates each weight in the direction opposite the gradient, scaled by the learning rate. Stochastic gradient descent estimates the gradient from a small mini-batch instead of the full dataset, which makes training dramatically faster on large corpora.

A learning rate that is too large makes training diverge, while one that is too small makes convergence painfully slow. Learning-rate schedules and adaptive optimizers such as Adam reduce the need to tune this value by hand.

## Generalization and Overfitting

Overfitting is the failure mode where a model memorizes its training data and performs poorly on unseen examples. A model with millions of parameters can fit noise, so measuring held-out performance is essential.

Regularization adds a penalty on large weights to discourage overly complex models. Dropout randomly deactivates a fraction of neurons during training, which acts as a cheap ensemble and further reduces overfitting.

A validation set is held out from training so that generalization can be measured honestly. Early stopping halts training when validation loss stops improving, which prevents the model from drifting away from its best generalizing state.

## Modern Architectures

A convolutional neural network is a network that shares small learnable filters across space, making it efficient for images. Weight sharing means a detector learned in one corner of an image also works in every other corner.

A transformer is a sequence model built on self-attention, which lets every position attend to every other position in parallel. Self-attention computes a weighted average of value vectors, where the weights come from the similarity between query and key vectors.

A large language model is a transformer trained to predict the next token across billions of tokens of text. Because the objective requires no manual labels, the same architecture scales from translation to code generation.

## Responsible Practice

Algorithmic bias is the systematic unfairness that appears when a model learns patterns from skewed or unrepresentative data. Auditing a model on disaggregated subgroups often reveals errors that an aggregate accuracy score hides.

An evaluation metric is only meaningful when it matches the decision the system will actually support. A spam filter judged by raw accuracy can look excellent while missing most of the spam it was built to catch.

Reproducibility requires recording data versions, random seeds, hyperparameters, and evaluation code alongside the model. A model card documents a system's intended use, limitations, and measured performance so downstream users can judge its risks.

## Key Takeaways

Algorithms and neural networks share a common language of optimization, complexity, and evaluation. Choosing the right algorithmic pattern often matters more than constant-factor tuning, and the same is true when choosing a network architecture and training objective.
