import numpy as np;
import pandas as pd;
pd.options.plotting.backend = "plotly";

ff = 'https://raw.githubusercontent.com/0xbigz/drift-flat-data/72b1af510667f1653c038a5385dd5267219fc6ed/data/trade_history.csv';
ffc = 'https://raw.githubusercontent.com/0xbigz/drift-flat-data/72b1af510667f1653c038a5385dd5267219fc6ed/data/curve_history.csv';
ffm = 'https://raw.githubusercontent.com/0xbigz/drift-flat-data/72b1af510667f1653c038a5385dd5267219fc6ed/data/markets_state.csv';

PEG_PRECISION = 10 ** 3;
FUNDING_PRECISION = 10 ** 4;
QUOTE_PRECISION = 10 ** 6;
MARK_PRICE_PRECISION = 10 ** 10;
AMM_RESERVE_PRECISION = 10 ** 13;

AMM_TO_QUOTE_PRECISION_RATIO = AMM_RESERVE_PRECISION / QUOTE_PRECISION  # 10**7;
PRICE_TO_QUOTE_PRECISION = MARK_PRICE_PRECISION / QUOTE_PRECISION  # 10**7;
AMM_TIMES_PEG_TO_QUOTE_PRECISION_RATIO = (
    AMM_RESERVE_PRECISION * PEG_PRECISION / QUOTE_PRECISION
);

FULL_LIQUIDATION_RATIO = 500;
PARTIAL_LIQUIDATION_RATIO = 625;

MAX_LEVERAGE = 5;

trade_raw_data=pd.read_csv(ff,index_col=0,parse_dates=True,squeeze=True);
curve_raw_data=pd.read_csv(ffc,index_col=0,parse_dates=True,squeeze=True);
market_state=pd.read_csv(ffm,index_col=[0]);

trade_hist=trade_raw_data.loc[trade_raw_data['market_index']==int('0')];
curve_hist=curve_raw_data.loc[curve_raw_data['market_index']==int('0')];
index_0_state=market_state['0'];

print(index_0_state);

"""
peg_multiplier: the magnitude of the quote_asset_reserve. One virtual quote_asset_reserve is a peg_multiplier amount of the quote_asset.

A peg_multiplier ensures that the base_asset_reserve and the quote_asset_reserve are balanced at the initialisation of the curve while ensuring
that the starting price of the pool is equivalent to the oracle_price of the base asset at initialisation.

slippage(1)=cost for buying 1 base_asset.amount.

Repeg: Modifying the peg multiplier means re-pegging the curve such that the mark price is closer to the oracle price.

Adjusting k: Modifying the curve's invariant k by scaling the base/quote asset reserves. For instance, this modifies the default slippage of
a swap. 

price: if user like to purchase one unit of quote asset, how much unit asset the user needs to pay so that the transation can be fulfilled.

"""

def calculate_price(base_asset_amount, quote_asset_amount, peg_multiplier):
    if abs(base_asset_amount) <= 0:
        return 0
    else:
        return (quote_asset_amount / base_asset_amount) * peg_multiplier/PEG_PRECISION


quote_asset_reserve=float(index_0_state.quote_asset_reserve);

base_asset_reserve=float(index_0_state.base_asset_reserve);

peg_multiplier=float(index_0_state.peg_multiplier);

mark_price=quote_asset_reserve/base_asset_reserve*peg_multiplier;

print(mark_price);

k=np.power(float(index_0_state.sqrt_k),2);
k;



# swap has PositionDirection: short, long. input_asset has type: base, quote. Swap direction is a result of  input_asset_type and  position_direction combination. 
# SwapDirection can either be  remove or add . that is to add / remove swap_amount to the corresponding reserve, which obviously leads to a change in the reserve.

input_asset_type={"quote", "base"};
position_direction={"PositionDirection.LONG", "PositionDirection.SHORT"};

class SwapDirection():
  def __init__(self, add, remove ):
    self.add=add
    self.remove=remove

def swap_direction(input_asset_type, position_direction):

  if (position_direction =="PositionDirection.LONG"
      and input_asset_type=="base"):
    return SwapDirection.remove

  if (position_direction =="PositionDirection.SHORT"
      and input_asset_type=="quote"):
    return SwapDirection.remove

  return SwapDirection.add

"""
(1)define swap_output function with input_asset_reserve (the correspoding base_asset_reserve or quote_asset_reserve which is already in pool), swap_amount (the specific base_asset_amount or quote_asset_amount 
which is corresponding to input_asset_reserve. eg. if input_asset_reserve = base_assert_reserve, then swap_amount=base_asset_amount in that specific swap), 
swap_direction: SwapDirection (swap/transaction object main feature/method), and k constant.

(2) major diff between swap_output and mark_swap_output: swap_amount(specific amount that is used to make the swap) has to be non-negative, 

but market base_asset_amount =SUM(base_asset_amount_long,base_asset_amount_short) can be negative.

(3)A swap directly incur a change in both base_asset_reserve and quote_asset_reserve if consts are not changed in the meantime. as the result of the swap, price is fluctuated as well.

"""

def swap_output(input_asset_reserve, swap_amount, swap_direction: SwapDirection, k):

    assert swap_direction in [
        SwapDirection.add,
        SwapDirection.remove,
    ],"invalid swap direction parameter"

    assert swap_amount >= 0

    if swap_direction =='SwapDirection.add':
      new_input_asset_reserve=input_asset_reserve+swap_amount

    else:
      new_input_asset_reserve=input_asset_reserve-swap_amount

    new_output_asset_reserve=k/new_input_asset_reserve

    return [new_input_asset_reserve, new_output_asset_reserve]



def mark_swap_output(mark_input_asset_reserve, input_asset_type, swap_amount, swap_direction:SwapDirection):

  if input_asset_type=="quote":
    swap_amount=swap_amount*1e13*1e3/1e6/peg_multiplier
    [new_quote_asset_reserve, new_base_asset_reserve]=swap_output(
        index_0_state.quote_asset_reserve,
        swap_amount,
        swap_direction,
        (index_0_state.sqrt_k)**2)
  else:
    [new_quote_asset_reserve, new_base_asset_reserve]=swap_output(
      index_0_state.base_asset_reserve,
      swap_amount,
      swap_direction,
      (index_0_state.sqrt_k)**2)
    
  return [new_quote_asset_reserve, new_base_asset_reserve]


  def calculate_mark_price_afterswap(index_0_state):
    swap_direction=(
        SwapDirection.add if index_0_state.base_asset_amount > 0 else SwapDirection.remove
    )
    new_base_asset_amount, new_quote_asset_amount=swap_output(
        index_0_state.base_asset_reserve,
        abs(index_0_state.base_asset_amount),
        swap_direction,
        (index_0_state.sqrt_k)**2
    )
    mark_price_afterswap=calculate_price(new_base_asset_amount,new_quote_asset_amount, index_0_state.peg_multiplier)

    return mark_price_afterswap


data=trade_hist;
data['direction'];


"""
sinario practise: 

known below variables and pls return (1) new base and quote asset reserves, assume k is fixed. (2) slippage at real time trading

f=swap_amount/input_asset_reserve  
trade_hist raw data [mark_price_before, mark_price_after, direction, base_asset_amount, quote_asset_amount]

"""

data=trade_hist;

# f=swap amount /input_asset_reserve (f is what before swap, a ratio between swap amount and all the input_asset_reserve in the pool before initating the current swap )

#  (1) f= sqrt (ratio)-1

#using assert to check array division is element-wise
f_1 = (np.sqrt(data.mark_price_after)/np.sqrt(data.mark_price_before)) - 1;
f_2=np.divide(np.sqrt(data.mark_price_after),np.sqrt(data.mark_price_before))-1;
assert f_1.all()==f_2.all(), "f_1 is different from f_2" ;


def get_f(x):
  # print(x)
  if x.direction == "PositionDirection.Long()":
    f = (np.sqrt(x.mark_price_after)/np.sqrt(x.mark_price_before)) - 1
  else:
    f = abs((np.sqrt(x.mark_price_after)/np.sqrt(x.mark_price_before)) - 1)
  return f

f = data.apply(lambda x: get_f(x),axis=1);


f_old =abs((np.sqrt(data.mark_price_after)/np.sqrt(data.mark_price_before)) - 1 );
# if data.direction.any() == "PositionDirection.Long()":
swap_amount=data.base_asset_amount;
old_input_asset_reserve=swap_amount/f;
new_input_asset_reserve=swap_amount/f+swap_amount; # base
new_output_asset_reserve=k*AMM_RESERVE_PRECISION/new_input_asset_reserve*AMM_RESERVE_PRECISION;
# else:
#   swap_amount=data.quote_asset_amount/peg_multiplier
#   old_input_asset_reserve=swap_amount/f
#   new_input_asset_reserve=swap_amount/f-swap_amount # quote
#   new_output_asset_reserve=k*AMM_RESERVE_PRECISION/new_input_asset_reserve
  
#   mark_price_after_check=new_output_asset_reserve/new_input_asset_reserve*peg_multiplier

df = pd.concat({'new_output': new_output_asset_reserve,
                'new_input': new_input_asset_reserve,
                'f1': f_1,
                'f2': f_2,
                'f': f,
                'f_old': f_old,
},axis=1)
df['peg'] = peg_multiplier;
df['k'] = k;
df.sort_index().plot();



#print([new_input_asset_reserve, new_output_asset_reserve])

user_quote_precision = new_output_asset_reserve*peg_multiplier;

mark_p_check=user_quote_precision/(new_input_asset_reserve);
print(mark_p_check);

# plt.plot([mark_p_check,data.mark_price_before])
# plt.show()



#(2)max_slippage = abs((new_price-old_price)/old_price);  avg_slippage=abs((entry_price-old_price)/old_price); 1e7 and 1e17 are guessing precisions

entry_price=data.quote_asset_amount/data.base_asset_amount*1e7;

print(entry_price);

old_price=data.mark_price_before/1e17;
new_price=data.mark_price_after/1e17;

max_slippage=abs((new_price-old_price)/old_price);
avg_slippage=abs((entry_price/1e7-old_price)/old_price);

#print([entry_price, max_slippage, avg_slippage])
#print((max_slippage>avg_slippage).all())

pd.concat([mark_p_check,
           data.mark_price_before/1e10,
           data.mark_price_after/1e10,
           ],axis=1).sort_index().plot()


#data as an example. input_asset_reserve is not 0. 

input_asset_reserve=float(index_0_state.base_asset_reserve);
print(base_asset_reserve);
swap_amount=data.base_asset_amount;
new_input_asset_reserve=[x+input_asset_reserve for x in swap_amount];
new_output_asset_reserve=k/new_input_asset_reserve;
print([new_input_asset_reserve,new_output_asset_reserve]);

arr1 = [2, 27, 2, 21, 23];
arr2 = [2, 3, 4, 5, 6];
a=np.divide(arr1,arr2);
print(a);