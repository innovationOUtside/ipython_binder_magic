# `ipython_binder_magic`
Run commands on a remote MyBinder kernel from your own, locally served, notebook...

This magic provides a just about working example of using Binder magic to launch a MyBinder container from Github and then access it from a notebook running the magic.

Install from the Github repo:

`pip install --upgrade git+https://github.com/innovationOUtside/ipython_binder_magic.git`

The magic can then be loaded as:

`%load_ext binder_magic`

The MyBinder connection should be initiated by calling the `%binder` line magic with a `-r` argument containing the name of the Github repository you want to use as the Binder target.

`%binder -r https://github.com/ouseful-demos/ordo`


Once the Binder image is running, we can start to run commands against it using `%%binder` cell magic:

```python
%%binder
a=1
print(a)
```

The kernel behaves as you'd expect...

```python
%%binder
a+999
```

Or more elaborately:

```python
%%binder
!pip install pandas
import pandas as pd
pd.DataFrame({'a':[1,2], 'b':['foo','bar']})
```

Note that whilst a heartbeat is sent back to the Binder kernel every 30s, the connection seems to die quite quickly (after about 2 minutes of inactivity?). A warning should be raised if the connection is detected to have died.

## Rationale
This magic is purely a proof of concept to explore the potential utility of a Binder magic command that would allow someone to run commands on a remote MyBinder kernel from a local notebook.

The motivating use case was a user who could install a simple local Jupyter installation and the magic, but who needed to call on a remote kernel containing a rather more elaborate environment than the user could install.

An advantage of this approach over running a notebook is MyBinder directly is that the notebook resides on the local machine.

But it's enough for a POC... A bit like running a notebook on a kernel that keeps dying on you...

## KNOWN ISSUES

Re: the kernel dying quickly, I wonder if we can con the Binder instance into thinking something is alive by creating a dummy notebook / kernel and adding a new cell to it in the background every 30s or so, so that the Binder container thinks it's still being actively used (?!) and doesn't time out so quickly...?

Doing this properly might help, of course...

The implementation of the magic is a bit *ad hoc* and is based on the  [Sage Cell client](https://sagecell.sagemath.org/) [[code](https://github.com/sagemath/sagecell/blob/master/contrib/sagecell-client/sagecell-client.py)].

A hearbeat is maintained through a `thread`. I'm guessing I really should use something like `asyncio`???

I imagine a better way would be to draw on something like the `nb2kg` tooling that allows a notebook server to connect to a remote enterprise gateway, or the `jupyter_client` code that would set up and manage the connection to the notebook server in a more natural way.

The notebook cell count number is currently ambiguous; at the moment it reports the cell count in the local notebook, not the cell execution count number in the remote kernel. We could hack the two to be the same, by setting the remote cell execution count to the same as the local notebook count.

Having to explicity invoke the `%%binder` cell magic is a faff; something like the approach used in [`cell_shell_magic`](https://github.com/innovationOUtside/cell_shell_magic) to automatically run code in a cell through a cell magic would simplify this, and give us an "as if Binder kernel" experience?

Though it might look like things like dataframes are being returned from the remote kernel, this is a bit fake... the cell output is a `display` of HTML returned from the remote MyBinder kernel.



